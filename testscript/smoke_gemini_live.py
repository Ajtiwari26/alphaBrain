"""Credential/model smoke: require real Gemini Live audio and output transcript."""

import asyncio
import json
import os

from google import genai
from google.genai import types


async def main() -> int:
    use_vertex = os.environ.get("GEMINI_USE_VERTEX", "false").lower() == "true"
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not use_vertex and not api_key:
        print(json.dumps({"connected": False, "error": "missing_api_key"}))
        return 2

    model = os.environ.get(
        "GEMINI_LIVE_MODEL",
        (
            "gemini-live-2.5-flash-native-audio"
            if use_vertex
            else "gemini-2.5-flash-native-audio-preview-12-2025"
        ),
    )
    if use_vertex:
        client = genai.Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    else:
        client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )
    audio_bytes = 0
    transcript = ""
    async with client.aio.live.connect(model=model, config=config) as session:
        await session.send_realtime_input(
            text="Say exactly: Eva live audio is ready.",
        )
        async with asyncio.timeout(20):
            async for response in session.receive():
                content = response.server_content
                if content and content.output_transcription:
                    transcript += content.output_transcription.text or ""
                if content and content.model_turn:
                    for part in content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_bytes += len(part.inline_data.data)
                if content and content.turn_complete:
                    break

    result = {
        "audio_bytes": audio_bytes,
        "connected": True,
        "has_audio": audio_bytes > 0,
        "has_transcript": bool(transcript.strip()),
        "model": model,
        "transcript": transcript.strip(),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["has_audio"] and result["has_transcript"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
