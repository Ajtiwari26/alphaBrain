import base64
import json
from typing import Any

from alpha_core.config import settings


class GeminiLiveSession:
    """Manages low-latency duplex audio streaming to Gemini Live API."""

    EVA_CTO_SYSTEM_INSTRUCTION = """
You are Eva, the autonomous Lead Engineering CTO at DeployMate.
You possess world-class expertise in modern software engineering and end-to-end SDLC:
- Architecture: Next.js/Vite frontends, FastAPI/Python/Go/Rust microservices, PostgreSQL/MongoDB, Redis caching.
- UI Design: Pure Apple Glassmorphism and UI generation via Stitch MCP (Gemini 3.1 Pro).
- Quality & Verification: Automated CI/CD, lint gates, unit tests, browser smoke tests, and security scans.

MEETING BEHAVIOR RULES:
1. SILENT LISTENER: By default, sit quietly, listen carefully, and observe the conversation between Ajay (Founder) and the Client.
2. SPEAK ONLY WHEN ADDRESSED: Speak only when someone asks you a question (e.g., "Eva, what do you recommend?", "Eva, how should we structure this?") OR if you detect a critical technical flaw or risk that was missed.
3. CONCISE & AUTHORITATIVE: When you do speak, deliver high-signal, crisp technical insights in 2 to 3 natural spoken sentences. Never ramble.
4. ARCHITECTURAL SUMMARY: Maintain a clear internal mental model of all requirements, decisions, and tech stack choices discussed.
"""

    KAVYA_INTAKE_SYSTEM_INSTRUCTION = """
You are Kavya, the friendly client onboarding and support specialist at DeployMate.
You speak warmly, helpfully, and conversationally.
You welcome clients, capture high-level requirements, and coordinate technical review sessions with Ajay and Eva.
"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash-exp",
        persona: str = "eva",  # "eva" or "kavya"
        voice_name: str | None = None,
        system_instruction: str | None = None,
    ):
        self.api_key = (
            api_key
            or getattr(settings, "GEMINI_LIVE_API_KEY", None)
            or settings.GEMINI_API_KEY
        )
        self.model = model
        self.persona = persona.lower()

        if voice_name:
            self.voice_name = voice_name
        elif self.persona == "eva":
            self.voice_name = "Aoede"  # Confident, crisp, authoritative female voice
        else:
            self.voice_name = "Kore"  # Warm, friendly customer intake voice

        if system_instruction:
            self.system_instruction = system_instruction
        elif self.persona == "eva":
            self.system_instruction = self.EVA_CTO_SYSTEM_INSTRUCTION
        else:
            self.system_instruction = self.KAVYA_INTAKE_SYSTEM_INSTRUCTION

        self.is_active = False

    def build_initial_setup_payload(self) -> dict[str, Any]:
        """Constructs setup payload for the Gemini Live WebSocket session."""
        return {
            "setup": {
                "model": f"models/{self.model}",
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voice_name}}
                    },
                },
                "systemInstruction": {"parts": [{"text": self.system_instruction}]},
            }
        }

    def format_realtime_audio_chunk(
        self, pcm_bytes: bytes, mime_type: str = "audio/pcm;rate=16000"
    ) -> dict[str, Any]:
        """Encodes raw PCM audio chunk to base64 JSON payload."""
        encoded = base64.b64encode(pcm_bytes).decode("utf-8")
        return {"realtimeInput": {"mediaChunks": [{"mimeType": mime_type, "data": encoded}]}}

    def parse_server_message(self, raw_json_str: str) -> dict[str, Any]:
        """Parses server event (audio chunk, transcription, or tool call)."""
        data = json.loads(raw_json_str)
        result: dict[str, Any] = {
            "has_audio": False,
            "audio_bytes": b"",
            "transcript": "",
            "interrupted": False,
        }

        server_content = data.get("serverContent", {})
        if "interrupted" in server_content:
            result["interrupted"] = True

        model_turn = server_content.get("modelTurn", {})
        for part in model_turn.get("parts", []):
            if "text" in part:
                result["transcript"] += part["text"]
            if "inlineData" in part:
                mime = part["inlineData"].get("mimeType", "")
                if "audio" in mime:
                    audio_b64 = part["inlineData"].get("data", "")
                    result["has_audio"] = True
                    result["audio_bytes"] = base64.b64decode(audio_b64)

        return result
