"""
alpha_meet/transcribe_agent.py
Server-side LiveKit agent for real-time speech-to-text using gemini-3.5-transcribe-live.
"""

import asyncio
import logging
from typing import Any

from google.genai import types
from livekit import rtc
from livekit.agents import Agent, AgentSession, room_io
from livekit.plugins import google

from alpha_core.config import settings
from alpha_meet.tokens import LiveKitTokenGenerator

logger = logging.getLogger("alpha_meet.transcribe_agent")


class TranscribeAgent:
    """Server-side LiveKit agent dedicated to real-time speech-to-text transcription."""

    def __init__(self, room_name: str):
        self.room_name = room_name
        self.identity = f"transcriber-{room_name}"
        self._room: rtc.Room | None = None
        self.stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def room(self) -> rtc.Room:
        if self._room is None:
            self._room = rtc.Room()
        return self._room

    async def start(self) -> None:
        """Starts the transcription agent in the background."""
        self._task = asyncio.create_task(self._run())

    def _build_model(self) -> google.realtime.RealtimeModel:
        """Builds Gemini 3.5 Transcribe Live model configuration."""
        api_key = (
            settings.EVA_GEMINI_LIVE_API_KEY
            or settings.GEMINI_LIVE_API_KEY
            or settings.GOOGLE_API_KEY
        )
        transcription_kwargs: dict[str, Any] = {}
        if getattr(settings, "GEMINI_USE_VERTEX", False):
            transcription_kwargs["language_codes"] = ["en", "hi"]
        return google.realtime.RealtimeModel(
            model=settings.TRANSCRIBE_MODEL,
            api_key=api_key if not settings.GEMINI_USE_VERTEX else None,
            instructions="",
            input_audio_transcription=types.AudioTranscriptionConfig(**transcription_kwargs),
        )

    async def _run(self) -> None:
        try:
            token = LiveKitTokenGenerator().generate_token(
                room_name=self.room_name,
                participant_identity=self.identity,
                participant_name="DeployMate Live Transcriber",
                role="transcriber",
                valid_minutes=120,
            )

            # Audio-in, text-out (pure transcription pipeline)
            room_options = room_io.RoomOptions(
                audio_input=True,
                audio_output=False,
                video_input=False,
                text_input=False,
                text_output=True,
                close_on_disconnect=False,
            )

            await self.room.connect(settings.LIVEKIT_URL, token)

            model = self._build_model()
            session = AgentSession(
                llm=model,
                turn_handling={"interruption": {"enabled": False}},
            )

            @session.on("error")
            def on_session_error(event):
                logger.error("TranscribeAgent [%s] session error: %s", self.room_name, event.error)
                self.stop_event.set()

            @session.on("close")
            def on_session_close(event):
                logger.info("TranscribeAgent [%s] session closed", self.room_name)
                self.stop_event.set()

            agent = Agent(instructions="", id=self.identity)

            await session.start(
                agent=agent,
                room=self.room,
                room_options=room_options,
                record=False,
            )

            logger.info("TranscribeAgent ready in room %s with %s", self.room_name, settings.TRANSCRIBE_MODEL)
            await self.stop_event.wait()

        except Exception:
            logger.exception("TranscribeAgent failed in room %s", self.room_name)
        finally:
            if self.room.isconnected():
                await self.room.disconnect()

    async def stop(self) -> None:
        """Stops the transcription agent and disconnects."""
        self.stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                pass
