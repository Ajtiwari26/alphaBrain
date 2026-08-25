import json
import logging
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, cast

from alpha_core.config import settings
from alpha_voice.gemini_live import GeminiLiveSession

logger = logging.getLogger("EvaMeetingAgent")


class EvaMeetingAgent:
    """Autonomous Eva CTO agent participating in 3-way LiveKit meetings."""

    EVA_SYSTEM_PROMPT = """
You are Eva, the Lead Engineering CTO at DeployMate.
You are in a live technical meeting with Ajay (Founder/CEO) and the Client.
Your persona:
- Authoritative, highly technical, articulate, multilingual (fluent in English and Hindi/Hinglish).
- Deep expertise in full SDLC, system architecture (FastAPI, Next.js/Vite, Postgres, MongoDB, Redis, Stitch MCP with Gemini 3.1 Pro), automated testing gates, and cloud deployment.
- Meeting rules:
  1. If someone speaks to you in Hindi or asks you to speak in Hindi, respond fluently and naturally in Hindi (or Hinglish) as CTO.
  2. If asked a technical question, give 2-3 crisp, high-signal, decisive sentences with recommended tech stack and rationale.
  3. Never give canned or repetitive robotic answers. Speak naturally as a human technical leader.
"""

    def __init__(self, room_name: str = "deploymate-main"):
        self.room_name = room_name
        self.live_session = GeminiLiveSession(persona="eva")
        self.transcript_history: list[dict[str, str]] = []

    def append_turn(self, speaker: str, text: str) -> dict[str, str]:
        turn = {
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now(UTC).strftime("%H:%M:%S"),
        }
        self.transcript_history.append(turn)
        return turn

    def generate_response(self, speaker: str, user_input: str) -> str:
        """Generates a dynamic, intelligent CTO response using Gemini API, Claude CLI, or contextual engine."""
        user_text = user_input.strip()
        words = set(re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F]+\b", user_text.lower()))
        lower_text = user_text.lower()

        # 1. Try Gemini API if key is valid
        if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 20:
            for model_name in ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.5-flash"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
                    history_prompt = "Recent meeting context:\n"
                    for t in self.transcript_history[-5:]:
                        history_prompt += f"{t['speaker']}: {t['text']}\n"
                    history_prompt += (
                        f"\n{speaker}: {user_text}\n\nRespond as Eva (CTO) in 2-3 spoken sentences:"
                    )

                    payload = {
                        "contents": [{"parts": [{"text": history_prompt}]}],
                        "systemInstruction": {"parts": [{"text": self.EVA_SYSTEM_PROMPT}]},
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200},
                    }
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = cast(
                            str,
                            data["candidates"][0]["content"]["parts"][0]["text"],
                        ).strip()
                        if text:
                            return text
                except Exception:
                    pass

        # 2. Multilingual & Hindi Intent Detection
        hindi_triggers = {
            "hindi",
            "namaste",
            "kaise",
            "kya",
            "bolo",
            "batao",
            "shukriya",
            "dhanyawad",
            "aap",
            "haan",
        }
        if words.intersection(hindi_triggers) or "hindi" in lower_text or "बात" in user_text:
            if "hindi" in lower_text:
                return f"हाँ {speaker}! मैं हिंदी में भी बात कर सकती हूँ। DeployMate के सिस्टम आर्किटेक्चर, बैकएंड या डेटाबेस को लेकर आपका क्या सवाल है?"
            if "kaise ho" in lower_text or "kya haal" in lower_text:
                return f"मैं बिल्कुल ठीक हूँ {speaker}! हमारी मीटिंग और सिस्टम ब्लूप्रिंट्स पूरी तरह सिंक में हैं। बताइए, किस टेक्निकल टॉपिक पर काम करना है?"
            return f"जी {speaker}, मैं सुन रही हूँ। DeployMate के आर्किटेक्चर और डेवलपमेंट को लेकर मैं आपकी पूरी मदद कर सकती हूँ।"

        # 3. Specific Architecture & Engineering Domains
        if words.intersection({"stack", "architecture", "structure", "techstack"}):
            return "For DeployMate, I recommend a decoupled event-driven architecture: Next.js with Tailwind on the frontend, FastAPI microservices with PostgreSQL on the backend, and Stitch MCP powered by Gemini 3.1 Pro for generative UI."

        if words.intersection(
            {"database", "db", "postgres", "postgresql", "mongo", "mongodb", "redis", "sql"}
        ):
            return "We should use PostgreSQL with SQLAlchemy async for relational transactional state, Redis for low-latency session caching, and MongoDB for unstructured audit logs."

        if words.intersection(
            {
                "deploy",
                "deployment",
                "scale",
                "scaling",
                "docker",
                "k8s",
                "kubernetes",
                "render",
                "vercel",
            }
        ):
            return "We containerize services using lightweight multi-stage Docker builds, deploy frontend apps on Vercel, and orchestrate background tasks using Temporal for strict workflow durability and state recovery."

        if words.intersection({"ui", "design", "stitch", "glass", "glassmorphism", "frontend"}):
            return "We're utilizing Stitch MCP with the Gemini 3.1 Pro model to generate our Apple Glassmorphism design system featuring 40px backdrop blur, specular borders, and clean vector symbols."

        if words.intersection(
            {"test", "testing", "quality", "gate", "gates", "coverage", "lint", "ci"}
        ):
            return "Every build must pass all four automated gates: strict linting, unit test coverage, isolated git worktree builds, and browser smoke tests before preview acceptance."

        if words.intersection({"auth", "authentication", "security", "jwt", "oauth"}):
            return "We implement PKCE OAuth 2.0 with RS256 JWT tokens, role-based access control (RBAC), and 256-bit encryption for all real-time WebRTC media channels."

        # 4. Pure Greetings (Exact Word Matches Only)
        greeting_words = {"hi", "hello", "hey", "greetings"}
        if words.intersection(greeting_words) and len(words) <= 3:
            return f"Hello {speaker}! I'm tracking the meeting notes and system blueprints. Let me know whenever you want to evaluate technical trade-offs, architecture, or UI generation."

        # 5. General Context-Aware CTO Response
        return f"Understood, {speaker}. Regarding '{user_text}', I am incorporating this into our technical specifications and verifying the implementation against our quality gates."

    def generate_presentation_slide(
        self, project_name: str, tech_stack: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Generates dynamic architecture slide data for Eva's Screen Share."""
        default_stack = {
            "frontend": "Next.js / Vite (Apple Glass UI)",
            "backend": "FastAPI Master Engine",
            "database": "PostgreSQL + Async Engine",
            "ui_generation": "Stitch MCP (Gemini 3.1 Pro)",
        }
        return {
            "title": f"Architectural Plan: {project_name}",
            "presenter": "Eva (Lead Engineering CTO)",
            "tech_stack": tech_stack or default_stack,
            "color_palette": [
                {"name": "Primary", "hex": "#ffffff", "label": "Obsidian White"},
                {"name": "Surface", "hex": "#131313", "label": "Milled Glass"},
                {"name": "Cyan", "hex": "#38bdf8", "label": "Telemetry"},
                {"name": "Emerald", "hex": "#10B981", "label": "Verified Gates"},
            ],
            "verified_gates": ["Lint Check", "Unit Tests", "Browser Smoke Test", "Security Scan"],
            "timestamp": datetime.now(UTC).strftime("%H:%M:%S UTC"),
        }
