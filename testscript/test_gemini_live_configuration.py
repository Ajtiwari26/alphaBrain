"""Regression checks for Alpha Brain's supported Gemini Live configuration."""

import asyncio
import re
from pathlib import Path

import pytest
from google.genai import types

from alpha_core.config import settings
from alpha_meet.eva_live_agent import EvaRoomManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOOGLE_KEY_PATTERN = re.compile(r"AIza[A-Za-z0-9_-]{30,}")
INTENTIONAL_SECRET_FIXTURES = {
    Path("testscript/test_rbac_and_redaction.py"),
    Path("testscript/test_project_event_log_api.py"),
}


def test_gemini_live_uses_supported_native_audio_model():
    assert settings.GEMINI_LIVE_MODEL == "gemini-2.5-flash-native-audio-latest"


def test_eva_live_agent_enables_resumption_and_context_compression():
    options = EvaRoomManager._model_options()
    resumption = options["session_resumption"]
    compression = options["context_window_compression"]

    assert isinstance(resumption, types.SessionResumptionConfig)
    assert resumption.transparent is True
    assert isinstance(compression, types.ContextWindowCompressionConfig)
    assert compression.trigger_tokens == 24_000
    assert compression.sliding_window.target_tokens == 12_000


def test_python_source_contains_no_hardcoded_google_api_key():
    matches: list[str] = []
    for source in PROJECT_ROOT.rglob("*.py"):
        if any(part in {".git", ".venv"} for part in source.parts):
            continue
        if source.relative_to(PROJECT_ROOT) in INTENTIONAL_SECRET_FIXTURES:
            continue
        if GOOGLE_KEY_PATTERN.search(source.read_text(encoding="utf-8")):
            matches.append(str(source.relative_to(PROJECT_ROOT)))

    assert matches == []


@pytest.mark.asyncio
async def test_provider_readiness_waits_for_connected_session():
    connected_session = type("ConnectedSession", (), {"_active_session": object()})()
    model = type("Model", (), {"_sessions": {connected_session}})()

    await EvaRoomManager._wait_for_provider_connection(model, failed=asyncio.Event())


@pytest.mark.asyncio
async def test_provider_readiness_fails_when_session_errors():
    failed = asyncio.Event()
    failed.set()
    model = type("Model", (), {"_sessions": set()})()

    with pytest.raises(RuntimeError, match="provider connection failed"):
        await EvaRoomManager._wait_for_provider_connection(model, failed=failed)
