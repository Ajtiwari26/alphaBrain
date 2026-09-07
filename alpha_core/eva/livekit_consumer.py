"""
alpha_core/eva/livekit_consumer.py
Asynchronous LiveKit room consumer that observes meetings, buffers transcripts,
and autonomously extracts and proposes tasks.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 4.2)
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from livekit import rtc

from alpha_core.config import settings
from alpha_core.eva.spec_extractor import EvaSpecificationExtractor, ExtractedSpecification
from alpha_core.eva.task_proposer import EvaTaskProposer
from alpha_core.eva.token_factory import mint_eva_consumer_token
from alpha_core.eva.transcript_buffer import DebouncedTranscriptBuffer, TranscriptSegment
from alpha_protocol.task import TaskEnvelope

logger = logging.getLogger("alpha_core.eva.consumer")


class EvaLiveKitConsumer:
    """Asynchronous read-only LiveKit meeting observer and specification engine."""

    def __init__(
        self,
        room_name: str,
        project_id: str,
        livekit_url: str | None = None,
        debounce_seconds: float = 30.0,
        spec_extractor: EvaSpecificationExtractor | None = None,
        task_proposer: EvaTaskProposer | None = None,
        on_task_proposed: Callable[[TaskEnvelope], Any] | None = None,
    ) -> None:
        self.room_name = room_name
        self.project_id = project_id
        self.livekit_url = livekit_url or settings.LIVEKIT_URL
        self.transcript_buffer = DebouncedTranscriptBuffer(debounce_seconds=debounce_seconds)
        self.spec_extractor = spec_extractor or EvaSpecificationExtractor()
        self.task_proposer = task_proposer or EvaTaskProposer()
        self.on_task_proposed = on_task_proposed

        self.room = rtc.Room()
        self._is_running = False
        self._loop_task: asyncio.Task[None] | None = None
        self.proposed_tasks: list[TaskEnvelope] = []
        self._active_tasks: set[asyncio.Task[Any]] = set()

        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(
                    "Eva subscribed to audio track %s from participant %s (%s)",
                    track.sid,
                    participant.identity,
                    participant.name,
                )
                # Attach audio stream for transcription
                task = asyncio.create_task(self._process_audio_track(track, participant))
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)

    async def _process_audio_track(
        self,
        track: rtc.Track,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """Processes incoming audio frames from a participant track."""
        audio_stream = rtc.AudioStream(track)
        participant_name = participant.name or participant.identity or "Participant"
        logger.debug("Started AudioStream for %s", participant_name)

        try:
            async for _frame_event in audio_stream:
                if not self._is_running:
                    break
                # Audio frames are streamed here. In live deployments, frames can be piped
                # to Speech-to-Text or Gemini Live.
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Audio stream error for %s: %s", participant_name, e)

    def ingest_transcript_line(
        self,
        speaker_id: str,
        speaker_name: str,
        text: str,
    ) -> TranscriptSegment:
        """Manually or externally pushes a transcribed dialogue line into the buffer."""
        return self.transcript_buffer.add_segment(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            text=text,
        )

    async def start(self) -> None:
        """Mints an observer token and connects to the LiveKit room."""
        if self._is_running:
            return

        token = mint_eva_consumer_token(room_name=self.room_name)
        logger.info("Connecting Eva read-only consumer to LiveKit room %s", self.room_name)

        await self.room.connect(self.livekit_url, token)
        self._is_running = True
        self._loop_task = asyncio.create_task(self._extraction_monitor_loop())
        self._monitor_connection_task = asyncio.create_task(self._monitor_connection_loop())
        logger.info("Eva read-only consumer connected successfully.")

    async def stop(self) -> None:
        """Disconnects cleanly and stops the monitor loop."""
        self._is_running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        if (
            hasattr(self, "_monitor_connection_task")
            and self._monitor_connection_task
            and not self._monitor_connection_task.done()
        ):
            self._monitor_connection_task.cancel()
            try:
                await self._monitor_connection_task
            except asyncio.CancelledError:
                pass
            self._monitor_connection_task = None

        if self.room.isconnected():
            await self.room.disconnect()
        logger.info("Eva read-only consumer stopped.")

    async def _monitor_connection_loop(self) -> None:
        """Periodically evaluates connection state and reconnects if dropped."""
        while self._is_running:
            try:
                await asyncio.sleep(5.0)
                if not self.room.isconnected():
                    logger.warning(
                        "Eva lost connection to LiveKit room %s. Attempting to reconnect...",
                        self.room_name,
                    )
                    token = mint_eva_consumer_token(room_name=self.room_name)
                    try:
                        await self.room.connect(self.livekit_url, token)
                        logger.info("Eva read-only consumer reconnected successfully.")
                    except Exception as e:
                        logger.error("Eva reconnect failed: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Eva connection monitor loop: %s", e)

    async def _extraction_monitor_loop(self) -> None:
        """Periodically evaluates if the transcript buffer is ready for specification extraction."""
        while self._is_running:
            try:
                await asyncio.sleep(2.0)
                if self.transcript_buffer.is_extraction_due():
                    await self.trigger_extraction()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Eva extraction loop: %s", e)

    async def trigger_extraction(self) -> TaskEnvelope | None:
        """Extracts specification from unextracted dialogue and proposes an Alpha Protocol task."""
        unextracted_text = self.transcript_buffer.get_unextracted_formatted_transcript()
        if not unextracted_text.strip():
            return None

        # Advance watermark to mark dialogue as processed
        self.transcript_buffer.mark_extracted()

        # Run extraction
        loop = asyncio.get_running_loop()
        spec: ExtractedSpecification | None = await loop.run_in_executor(
            None,
            self.spec_extractor.extract_from_transcript,
            unextracted_text,
        )

        if not spec or not spec.is_actionable:
            logger.info("Extraction completed: no actionable task in dialogue.")
            return None

        # Build task envelope
        envelope = self.task_proposer.build_task_envelope(
            spec=spec,
            project_id=self.project_id,
        )
        self.proposed_tasks.append(envelope)
        logger.info(
            "Eva autonomously proposed new task: %s (%s)", envelope.task_id, envelope.objective
        )

        if self.on_task_proposed:
            try:
                res = self.on_task_proposed(envelope)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error("Error in on_task_proposed callback: %s", e)

        return envelope
