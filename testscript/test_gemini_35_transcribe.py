"""
testscript/test_gemini_35_transcribe.py
Verification suite for Gemini 3.5 Transcribe Live (gemini-3.5-transcribe-live) decoupled transcription.
"""

import pytest
from google import genai
from google.genai import types

from alpha_core.config import settings
from alpha_meet.tokens import LiveKitTokenGenerator
from alpha_meet.transcribe_agent import TranscribeAgent
from alpha_voice.gemini_transcribe import GeminiLiveTranscriber


def test_transcribe_settings_configured():
    """Verify Gemini 3.5 Transcribe Live configuration in settings."""
    assert settings.TRANSCRIBE_MODEL == "gemini-3.5-transcribe-live"
    assert settings.GEMINI_TRANSCRIBE_MODEL == "gemini-3.5-transcribe-live"
    assert settings.TRANSCRIBE_MODE == "smart"
    assert settings.TRANSCRIBE_ENABLED is True


def test_live_transcriber_connect_config():
    """Verify GeminiLiveTranscriber builds compliant STT LiveConnectConfig."""
    transcriber = GeminiLiveTranscriber(
        model="gemini-3.5-transcribe-live",
        language_codes=["en", "hi"],
    )
    assert transcriber.model == "gemini-3.5-transcribe-live"
    assert transcriber.api_key == (
        settings.EVA_GEMINI_LIVE_API_KEY or settings.GEMINI_LIVE_API_KEY or settings.GEMINI_API_KEY
    )

    config = transcriber.build_connect_config()
    assert config.response_modalities == [types.Modality.TEXT]
    assert isinstance(config.input_audio_transcription, types.AudioTranscriptionConfig)
    if getattr(settings, "GEMINI_USE_VERTEX", False):
        assert config.input_audio_transcription.language_codes == ["en", "hi"]


def test_transcribe_agent_livekit_integration():
    """Verify TranscribeAgent initializes with gemini-3.5-transcribe-live and generates valid token."""
    agent = TranscribeAgent(room_name="deploymate-test-room")
    assert agent.identity == "transcriber-deploymate-test-room"

    model = agent._build_model()
    assert model.model == "gemini-3.5-transcribe-live"

    token = LiveKitTokenGenerator().generate_token(
        room_name="deploymate-test-room",
        participant_identity=agent.identity,
        role="transcriber",
    )
    assert isinstance(token, str)
    assert len(token) > 20


@pytest.mark.asyncio
async def test_live_transcribe_websocket_handshake():
    """Live duplex handshake with gemini-3.5-transcribe-live over WebSockets."""
    client = genai.Client(api_key=settings.EVA_GEMINI_LIVE_API_KEY)
    transcription_kwargs = {}
    if getattr(settings, "GEMINI_USE_VERTEX", False):
        transcription_kwargs["language_codes"] = ["en", "hi"]
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.TEXT],
        input_audio_transcription=types.AudioTranscriptionConfig(**transcription_kwargs),
    )
    async with client.aio.live.connect(model="gemini-3.5-transcribe-live", config=config) as session:
        assert session is not None
        # Send empty audio silence chunk (16kHz, 16-bit mono = 3200 bytes for 100ms)
        silence = b"\x00" * 3200
        await session.send_realtime_input(
            audio=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
        )
        # Notify turn end via Hybrid VAD signal
        await session.send_realtime_input(audio_stream_end=True)
