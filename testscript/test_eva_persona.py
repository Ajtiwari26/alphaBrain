"""
testscript/test_eva_persona.py
Tests for Eva CTO and Kavya Intake personas, voice configs, and meeting behavior rules.
"""

import pytest
from alpha_voice.gemini_live import GeminiLiveSession


def test_eva_cto_persona_and_voice():
    session = GeminiLiveSession(persona="eva")
    assert session.voice_name == "Aoede"
    assert "Lead Engineering CTO" in session.system_instruction
    assert "SILENT LISTENER" in session.system_instruction
    assert "SPEAK ONLY WHEN ADDRESSED" in session.system_instruction
    assert "Stitch MCP (Gemini 3.1 Pro)" in session.system_instruction

    setup_payload = session.build_initial_setup_payload()
    assert setup_payload["setup"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Aoede"


def test_kavya_intake_persona_and_voice():
    session = GeminiLiveSession(persona="kavya")
    assert session.voice_name == "Kore"
    assert "Kavya" in session.system_instruction
    assert "onboarding and support specialist" in session.system_instruction

    setup_payload = session.build_initial_setup_payload()
    assert setup_payload["setup"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"
