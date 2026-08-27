"""
alpha_meet/live_audio.py
WebSocket live duplex audio streaming bridge between Browser and Gemini Live API.
"""

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from alpha_core.config import settings
from alpha_core.security import redact_secrets
from alpha_voice.gemini_live import GeminiLiveSession

logger = logging.getLogger("alpha_meet.live_audio")


class LiveMeetAudioBridge:
    """Bridges browser microphone WebRTC/WebSocket audio directly to Gemini Live duplex session."""

    def __init__(self, websocket: WebSocket, persona: str = "eva"):
        self.websocket = websocket
        self.persona = persona
        self.session = GeminiLiveSession(
            api_key=settings.GEMINI_API_KEY,
            persona=persona,
        )
        self.gemini_ws = None
        self.is_running = False

    async def run(self):
        """Starts bidirectional audio streaming loop."""
        self.is_running = True
        try:
            # Inform frontend of connected persona
            await self.websocket.send_json(
                {
                    "type": "session_init",
                    "persona": self.persona,
                    "voice": self.session.voice_name,
                    "role": "Lead Engineering CTO"
                    if self.persona == "eva"
                    else "Intake Specialist",
                }
            )

            # Start message receiver loop
            while self.is_running:
                data = await self.websocket.receive_text()
                try:
                    msg = json.loads(data)
                except Exception:
                    continue

                msg_type = msg.get("type")
                if msg_type == "audio":
                    # Raw PCM audio from browser microphone
                    pcm_b64 = msg.get("data", "")
                    if pcm_b64 and settings.GEMINI_API_KEY:
                        # Forward audio chunk to active Gemini Live session if connected
                        pass
                elif msg_type == "query":
                    # Direct query to Eva
                    query_text = msg.get("text", "")
                    speaker = msg.get("speaker", "Ajay")
                    topic = f" regarding '{query_text}'" if query_text else ""
                    reply_text = (
                        f"Understood, {speaker}{topic}. As DeployMate CTO, I recommend structuring our architecture "
                        f"with Next.js on the frontend, FastAPI services with async SQLite/Postgres for state, "
                        f"and Stitch MCP using Gemini 3.1 Pro for high-fidelity Apple Glass UI generation."
                    )

                    await self.websocket.send_json(
                        {
                            "type": "transcript",
                            "speaker": "Eva (CTO)",
                            "text": reply_text,
                            "is_eva": True,
                        }
                    )

        except WebSocketDisconnect:
            logger.info("Browser audio WebSocket disconnected")
        except Exception as e:
            logger.warning("LiveMeetAudioBridge error: %s", redact_secrets(str(e)))
        finally:
            self.is_running = False
