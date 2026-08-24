"""
testscript/test_voice_pipeline.py
Automated tests for Gemini Live session payloads, Plivo audio bridge, and SpecExtractor.
"""

import base64
import json

from alpha_protocol import CallJob, PersonaType
from alpha_voice.extractor import SpecExtractor
from alpha_voice.gemini_live import GeminiLiveSession
from alpha_voice.plivo_bridge import PlivoVoiceBridge


def test_gemini_live_session_setup_payload():
    session = GeminiLiveSession(
        model="gemini-2.0-flash-exp",
        voice_name="Aoede",
        system_instruction="You are Eva.",
    )
    payload = session.build_initial_setup_payload()
    assert payload["setup"]["model"] == "models/gemini-2.0-flash-exp"
    assert payload["setup"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Aoede"


def test_gemini_live_audio_chunking():
    session = GeminiLiveSession()
    dummy_pcm = b"\x00\x01\x02\x03" * 100
    chunk_payload = session.format_realtime_audio_chunk(dummy_pcm)

    assert "realtimeInput" in chunk_payload
    media_chunks = chunk_payload["realtimeInput"]["mediaChunks"]
    assert len(media_chunks) == 1
    assert media_chunks[0]["mimeType"] == "audio/pcm;rate=16000"


def test_plivo_voice_bridge_media_parsing():
    job = CallJob(
        notification_id="ntf_voice_01",
        persona=PersonaType.EVA,
        recipient_phone="+1234567890",
        purpose="preview_check",
        script_facts={"preview_url": "http://localhost:3000"},
        idempotency_key="idemp_voice_01",
    )
    bridge = PlivoVoiceBridge(job)

    # 1. Start event
    start_msg = json.dumps({
        "event": "start",
        "streamId": "stream_12345",
        "callId": "call_abc987",
    })
    bridge.handle_plivo_media_message(start_msg)
    assert bridge.stream_id == "stream_12345"
    assert bridge.call_uuid == "call_abc987"

    # 2. Inbound media audio
    raw_pcm = b"\x10\x20\x30\x40"
    media_msg = json.dumps({
        "event": "media",
        "media": {
            "payload": base64.b64encode(raw_pcm).decode("utf-8")
        }
    })
    extracted_pcm = bridge.handle_plivo_media_message(media_msg)
    assert extracted_pcm == raw_pcm

    # 3. Outbound formatted audio
    outbound_str = bridge.format_plivo_outbound_audio(raw_pcm)
    outbound_json = json.loads(outbound_str)
    assert outbound_json["event"] == "playAudio"
    assert outbound_json["streamId"] == "stream_12345"


def test_spec_extractor_parsing():
    mock_model_response = """```json
{
  "requirements": [
    {
      "req_id": "req_voice_01",
      "title": "Barge-in Support",
      "raw_quote": "The agent must immediately stop speaking when the client talks",
      "description": "Handle interruption events via Gemini Live serverContent.interrupted signal",
      "acceptance_criteria": ["Mutes local audio playback within 150ms"],
      "priority": "must_have"
    }
  ],
  "decisions": [
    {
      "dec_id": "dec_voice_01",
      "topic": "Telephony Provider",
      "decision": "Use Plivo bi-directional media streams",
      "rationale": "High reliability and native WebSocket audio streaming support"
    }
  ],
  "open_questions": []
}
```"""

    spec = SpecExtractor.parse_extraction_json(
        mock_model_response,
        project_id="prj_alpha",
        title="Voice Engine Architecture",
    )

    assert spec.version == 1
    assert len(spec.requirements) == 1
    assert spec.requirements[0].req_id == "req_voice_01"
    assert len(spec.decisions) == 1
    assert spec.decisions[0].dec_id == "dec_voice_01"
