"""Deterministic contracts for AlphaMeet Gemini Live translation wiring."""

from types import SimpleNamespace
from typing import Any

from alpha_meet import translate_agent
from alpha_meet.translate_agent import TranslateAgent


def test_translation_patch_forwards_only_translation_configuration(monkeypatch):
    config = SimpleNamespace(
        system_instruction="must-clear",
        tools=["must-clear"],
        history_config="must-clear",
        translation_config=None,
    )
    translation_config = object()
    session = SimpleNamespace(
        _realtime_model=SimpleNamespace(translation_config=translation_config)
    )
    monkeypatch.setattr(translate_agent, "original_build", lambda _session: config)

    result = translate_agent.patched_build(session)

    assert result is config
    assert result.system_instruction is None
    assert result.tools is None
    assert result.history_config is None
    assert result.translation_config is translation_config


def test_translate_agent_builds_official_audio_translation_config(monkeypatch):
    captured: dict[str, Any] = {}

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(translate_agent.google.realtime, "RealtimeModel", FakeModel)
    agent = TranslateAgent(room_name="room-1", target_language="es")

    model = agent._build_model()

    assert captured["model"] == translate_agent.settings.TRANSLATE_MODEL
    assert captured["instructions"] == ""
    assert captured["input_audio_transcription"] is not None
    assert captured["output_audio_transcription"] is not None
    assert model.translation_config.target_language_code == "es"
    assert model.translation_config.echo_target_language is False
