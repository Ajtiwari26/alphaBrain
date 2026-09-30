"""
testscript/test_eva_gemini_38_live.py
Verification script for Eva's Gemini 3.8 Live speech-to-speech integration.
"""

import pytest
from google import genai
from google.genai import types
from livekit.plugins.google.realtime import RealtimeModel

from alpha_core.config import settings
from alpha_meet.eva_live_agent import EvaRoomManager
from alpha_voice.gemini_live import GeminiLiveSession


def test_eva_key_and_model_isolation():
    """Verify Eva strictly uses gemini-3.8-live and valid Gemini Live API key."""
    # 1. Check environment settings
    assert settings.GEMINI_LIVE_MODEL == "gemini-3.8-live"
    assert settings.EVA_GEMINI_LIVE_MODEL == "gemini-3.8-live"
    assert bool(settings.EVA_GEMINI_LIVE_API_KEY)
    assert bool(settings.GEMINI_API_KEY)

    # 2. Check Eva LiveKit Room Manager options
    eva_options = EvaRoomManager._model_options()
    assert eva_options["model"] == "gemini-3.8-live"
    assert eva_options["api_key"] == settings.EVA_GEMINI_LIVE_API_KEY
    assert "enable_affective_dialog" not in eva_options
    assert "proactivity" not in eva_options

    # 3. Check GeminiLiveSession persona isolation
    eva_session = GeminiLiveSession(persona="eva")
    assert eva_session.model == "gemini-3.8-live"
    assert eva_session.api_key == settings.EVA_GEMINI_LIVE_API_KEY
    assert eva_session.voice_name == "Aoede"

    # 4. Check Non-Eva persona (Kavya)
    kavya_session = GeminiLiveSession(persona="kavya")
    assert kavya_session.api_key == settings.GEMINI_API_KEY


def test_livekit_realtime_model_initialization():
    """Verify LiveKit's RealtimeModel initializes with Eva's gemini-3.8-live options."""
    eva_options = EvaRoomManager._model_options()
    model = RealtimeModel(
        model=eva_options["model"],
        api_key=eva_options["api_key"],
        voice=eva_options["voice"],
        instructions=eva_options["instructions"],
    )
    assert model.model == "gemini-3.8-live"


@pytest.mark.asyncio
async def test_live_api_websocket_handshake():
    """Live duplex handshake with gemini-3.8-live using Eva's dedicated key."""
    client = genai.Client(api_key=settings.EVA_GEMINI_LIVE_API_KEY)
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            parts=[types.Part(text="You are Eva, CTO at DeployMate.")]
        ),
    )
    # Open and close the live WebSocket session
    async with client.aio.live.connect(model="gemini-3.8-live", config=config) as session:
        assert session is not None
        # Send a brief realtime text probe
        await session.send_realtime_input(text="Hello Eva, testing speech-to-speech connection.")
