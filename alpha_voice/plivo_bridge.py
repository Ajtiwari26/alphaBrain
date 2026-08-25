import base64
import json

from alpha_protocol import CallJob, PersonaType

from .gemini_live import GeminiLiveSession


class PlivoVoiceBridge:
    """Bridges Plivo bidirectional WebSocket telephony streams with Gemini Live."""

    EVA_SYSTEM_PROMPT = """
You are Eva, the autonomous lead engineering persona at DeployMate.
You speak crisply, concisely, and with technical precision.
You are calling to provide an update or request approval on a verified development task.
STRICT RULE: Only state facts that are verified in the provided script facts. Never fabricate completion.
"""

    KAVYA_SYSTEM_PROMPT = """
You are Kavya, the friendly intake and client onboarding specialist at DeployMate.
You speak naturally, warmly, and helpfully.
You are calling to welcome the client, capture requirements, or schedule a technical review.
"""

    def __init__(self, job: CallJob):
        self.job = job
        self.stream_id: str | None = None
        self.call_uuid: str | None = None

        system_prompt = (
            self.EVA_SYSTEM_PROMPT if job.persona == PersonaType.EVA else self.KAVYA_SYSTEM_PROMPT
        )
        if job.script_facts:
            system_prompt += f"\nVERIFIED FACTS: {json.dumps(job.script_facts, indent=2)}\n"

        self.live_session = GeminiLiveSession(
            voice_name="Aoede" if job.persona == PersonaType.EVA else "Kore",
            system_instruction=system_prompt,
        )

    def handle_plivo_media_message(self, message_str: str) -> bytes | None:
        """Parses inbound Plivo WebSocket message and extracts raw audio bytes."""
        try:
            msg = json.loads(message_str)
            event = msg.get("event")

            if event == "start":
                self.stream_id = msg.get("streamId")
                self.call_uuid = msg.get("callId")
                return None
            elif event == "media":
                media_data = msg.get("media", {})
                payload_b64 = media_data.get("payload", "")
                if payload_b64:
                    return base64.b64decode(payload_b64)
            return None
        except Exception:
            return None

    def format_plivo_outbound_audio(self, pcm_bytes: bytes) -> str:
        """Formats outbound audio chunk into Plivo media event JSON."""
        encoded = base64.b64encode(pcm_bytes).decode("utf-8")
        payload = {
            "event": "playAudio",
            "media": {
                "contentType": "audio/x-l16;rate=8000",
                "sampleRate": 8000,
                "payload": encoded,
            },
        }
        if self.stream_id:
            payload["streamId"] = self.stream_id
        return json.dumps(payload)
