"""Prove Eva receives LiveKit text and returns real PCM audio plus transcription."""

import asyncio
import json
import os
import time
from contextlib import suppress

import httpx
from livekit import rtc

EVA_IDENTITY = "eva-cto"
EVA_LINKED_PARTICIPANT_ATTRIBUTE = "alpha.eva.linkedParticipant"
MIN_AUDIO_BYTES = 24_000
MIN_VOICED_FRAMES = 5


async def run_smoke() -> dict[str, object]:
    api_base = os.getenv("ALPHA_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    api_token = os.getenv("ALPHA_API_TOKEN", "")
    if not api_token:
        raise RuntimeError("ALPHA_API_TOKEN is required")

    room_name = f"eva-voice-smoke-{int(time.time())}"
    identity = f"Eva Voice Smoke {int(time.time())}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{api_base}/api/meet/token",
            headers={"Authorization": f"Bearer {api_token}"},
            json={"room_name": room_name, "identity": identity},
        )
        response.raise_for_status()
        join = response.json()

    room = rtc.Room()
    audio_ready = asyncio.Event()
    transcript_ready = asyncio.Event()
    audio_bytes = 0
    audio_frames = 0
    voiced_frames = 0
    peak_sample = 0
    transcripts: list[str] = []
    transcript_tasks: set[asyncio.Task[None]] = set()
    audio_task: asyncio.Task[None] | None = None
    microphone_task: asyncio.Task[None] | None = None
    microphone_source: rtc.AudioSource | None = None

    async def collect_audio(track: rtc.RemoteAudioTrack) -> None:
        nonlocal audio_bytes, audio_frames, peak_sample, voiced_frames
        stream = rtc.AudioStream(track, sample_rate=24_000, num_channels=1)
        try:
            async for event in stream:
                audio_frames += 1
                audio_bytes += event.frame.data.nbytes
                frame_peak = max((abs(sample) for sample in event.frame.data), default=0)
                peak_sample = max(peak_sample, frame_peak)
                if frame_peak >= 100:
                    voiced_frames += 1
                if audio_bytes >= MIN_AUDIO_BYTES and voiced_frames >= MIN_VOICED_FRAMES:
                    audio_ready.set()
        finally:
            await stream.aclose()

    async def publish_microphone_silence(source: rtc.AudioSource) -> None:
        frame = rtc.AudioFrame.create(
            sample_rate=24_000,
            num_channels=1,
            samples_per_channel=1_200,
        )
        while True:
            await source.capture_frame(frame)
            await asyncio.sleep(0.05)

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        _publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        nonlocal audio_task
        if participant.identity == EVA_IDENTITY and track.kind == rtc.TrackKind.KIND_AUDIO:
            audio_task = asyncio.create_task(collect_audio(track))

    @room.on("transcription_received")
    def on_transcription_received(
        segments: list[rtc.TranscriptionSegment],
        participant: rtc.Participant | None,
        _publication: rtc.TrackPublication | None,
    ) -> None:
        if participant is None or participant.identity != EVA_IDENTITY:
            return
        for segment in segments:
            if segment.text:
                transcripts.append(segment.text)
            if segment.final and segment.text:
                transcript_ready.set()

    async def collect_transcript_stream(reader: rtc.TextStreamReader) -> None:
        text = await reader.read_all()
        if text:
            transcripts.append(text)
            transcript_ready.set()

    def on_transcript_stream(reader: rtc.TextStreamReader, sender_identity: str) -> None:
        if sender_identity != EVA_IDENTITY:
            return
        task = asyncio.create_task(collect_transcript_stream(reader))
        transcript_tasks.add(task)
        task.add_done_callback(transcript_tasks.discard)

    room.register_text_stream_handler("lk.transcription", on_transcript_stream)

    await room.connect(join["livekit_url"], join["token"])
    try:
        microphone_source = rtc.AudioSource(sample_rate=24_000, num_channels=1)
        microphone_track = rtc.LocalAudioTrack.create_audio_track(
            "smoke-microphone",
            microphone_source,
        )
        await room.local_participant.publish_track(
            microphone_track,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )
        microphone_task = asyncio.create_task(publish_microphone_silence(microphone_source))
        async with asyncio.timeout(5.0):
            while True:
                eva = room.remote_participants.get(EVA_IDENTITY)
                if (
                    eva is not None
                    and eva.attributes.get(EVA_LINKED_PARTICIPANT_ATTRIBUTE) == identity
                ):
                    break
                await asyncio.sleep(0.05)
        await room.local_participant.send_text(
            "Eva, say exactly: Alpha Brain Eva voice transport works.",
            topic="lk.chat",
        )
        try:
            async with asyncio.timeout(30.0):
                await asyncio.gather(audio_ready.wait(), transcript_ready.wait())
        except TimeoutError as exc:
            diagnostics = {
                "audio_bytes": audio_bytes,
                "audio_frames": audio_frames,
                "audio_ready": audio_ready.is_set(),
                "peak_sample": peak_sample,
                "voiced_frames": voiced_frames,
                "transcript_ready": transcript_ready.is_set(),
                "transcripts": transcripts,
            }
            raise RuntimeError(f"Eva response proof timed out: {json.dumps(diagnostics)}") from exc
        return {
            "connected": True,
            "room": room_name,
            "eva_audio_frames": audio_frames,
            "eva_audio_bytes": audio_bytes,
            "eva_peak_sample": peak_sample,
            "eva_voiced_frames": voiced_frames,
            "eva_transcript": transcripts[-1],
            "has_real_audio": (
                audio_bytes >= MIN_AUDIO_BYTES and voiced_frames >= MIN_VOICED_FRAMES
            ),
            "has_transcript": bool(transcripts),
        }
    finally:
        if microphone_task is not None:
            microphone_task.cancel()
            with suppress(asyncio.CancelledError):
                await microphone_task
        if microphone_source is not None:
            await microphone_source.aclose()
        await room.disconnect()
        if audio_task is not None:
            audio_task.cancel()
            with suppress(asyncio.CancelledError):
                await audio_task
        for task in transcript_tasks:
            task.cancel()
        if transcript_tasks:
            await asyncio.gather(*transcript_tasks, return_exceptions=True)


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_smoke()), sort_keys=True))
