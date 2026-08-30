import asyncio
import logging
from typing import Any

import livekit.plugins.google.realtime.realtime_api as realtime_api
from google.genai import types
from livekit import rtc
from livekit.agents import Agent, AgentSession, room_io
from livekit.plugins import google

from alpha_core.config import settings
from alpha_meet.tokens import LiveKitTokenGenerator

logger = logging.getLogger("alpha_meet.translate_agent")

# Monkey-patch livekit-plugins-google to support TranslationConfig
original_build = realtime_api.RealtimeSession._build_connect_config


def patched_build(self: Any) -> Any:
    conf = original_build(self)
    # Clear fields that break the audio-only translation pipeline
    conf.system_instruction = None
    conf.tools = None
    conf.history_config = None

    translation_config = getattr(self._realtime_model, "translation_config", None)
    if translation_config is not None:
        conf.translation_config = translation_config
    return conf


realtime_api.RealtimeSession._build_connect_config = patched_build


class TranslateAgent:
    """Server-side LiveKit agent that translates room audio to a specific target language."""

    def __init__(self, room_name: str, target_language: str):
        self.room_name = room_name
        self.target_language = target_language
        self.identity = f"translate-{target_language}"
        self.room = rtc.Room()
        self.stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Starts the translation agent in the background."""
        self._task = asyncio.create_task(self._run())

    def _build_model(self) -> google.realtime.RealtimeModel:
        """Build Gemini Live Translate with official audio transcript configuration."""
        model = google.realtime.RealtimeModel(
            model=settings.TRANSLATE_MODEL,
            api_key=settings.GOOGLE_API_KEY if not settings.GEMINI_USE_VERTEX else None,
            instructions="",
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        model.translation_config = types.TranslationConfig(
            target_language_code=self.target_language,
            echo_target_language=False,
        )
        return model

    async def _run(self) -> None:
        try:
            token = LiveKitTokenGenerator().generate_token(
                room_name=self.room_name,
                participant_identity=self.identity,
                participant_name=f"Translator ({self.target_language.upper()})",
                role="translator",
                valid_minutes=120,
            )

            # We don't want the agent to shut down when someone leaves, we manage it externally.
            room_options = room_io.RoomOptions(
                audio_input=True,
                audio_output=True,
                video_input=False,
                text_input=False,  # Audio-only pipeline
                text_output=False,
                close_on_disconnect=False,
            )

            await self.room.connect(settings.LIVEKIT_URL, token)

            # Configure the translation model
            model = self._build_model()

            session = AgentSession(
                llm=model,
                turn_handling={"interruption": {"enabled": True}},
            )

            @session.on("error")
            def on_session_error(event):
                logger.error(
                    "TranslateAgent [%s] session error: %s", self.target_language, event.error
                )
                self.stop_event.set()

            @session.on("close")
            def on_session_close(event):
                logger.info("TranslateAgent [%s] session closed", self.target_language)
                self.stop_event.set()

            agent = Agent(instructions="", id=self.identity)

            await session.start(
                agent=agent,
                room=self.room,
                room_options=room_options,
                record=False,
            )

            logger.info(
                "TranslateAgent [%s] ready in room %s", self.target_language, self.room_name
            )
            await self.stop_event.wait()

        except Exception:
            logger.exception("TranslateAgent [%s] failed", self.target_language)
        finally:
            if self.room.isconnected():
                await self.room.disconnect()

    async def stop(self) -> None:
        """Stops the translation agent and disconnects."""
        self.stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                pass
