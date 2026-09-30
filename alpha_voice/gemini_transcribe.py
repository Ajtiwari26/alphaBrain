"""
alpha_voice/gemini_transcribe.py
Streaming real-time speech-to-text using Gemini 3.5 Transcribe Live (gemini-3.5-transcribe-live).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from alpha_core.config import settings

logger = logging.getLogger("alpha_voice.gemini_transcribe")


@dataclass
class TranscribeEvent:
    text: str
    is_final: bool = False
    is_interim: bool = False
    speaker: str | None = None


class GeminiLiveTranscriber:
    """Manages real-time bidirectional streaming transcription using gemini-3.5-transcribe-live."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        language_codes: list[str] | None = None,
    ):
        self.api_key = (
            api_key
            or getattr(settings, "EVA_GEMINI_LIVE_API_KEY", None)
            or getattr(settings, "GEMINI_LIVE_API_KEY", None)
            or settings.GEMINI_API_KEY
        )
        self.model = (
            model
            or getattr(settings, "GEMINI_TRANSCRIBE_MODEL", None)
            or getattr(settings, "TRANSCRIBE_MODEL", "gemini-3.5-transcribe-live")
        )
        self.language_codes = language_codes or ["en", "hi"]
        self.client: genai.Client | None = None
        self._session: Any = None
        self.is_connected: bool = False

    def build_connect_config(self) -> types.LiveConnectConfig:
        """Constructs LiveConnectConfig for streaming speech-to-text."""
        transcription_kwargs: dict[str, Any] = {}
        if getattr(settings, "GEMINI_USE_VERTEX", False) and self.language_codes:
            transcription_kwargs["language_codes"] = self.language_codes
        return types.LiveConnectConfig(
            response_modalities=[types.Modality.TEXT],
            input_audio_transcription=types.AudioTranscriptionConfig(**transcription_kwargs),
        )

    async def connect(self) -> None:
        """Initializes and connects the live transcription WebSocket session."""
        self.client = genai.Client(api_key=self.api_key)
        config = self.build_connect_config()
        self._session = await self.client.aio.live.connect(
            model=self.model,
            config=config,
        ).__aenter__()
        self.is_connected = True
        logger.info("Connected to %s transcription session", self.model)

    async def send_audio_chunk(
        self, pcm_bytes: bytes, mime_type: str = "audio/pcm;rate=16000"
    ) -> None:
        """Streams a raw PCM audio chunk to the transcription model."""
        if not self.is_connected or not self._session:
            raise RuntimeError("Transcriber session is not active")
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm_bytes, mime_type=mime_type)
        )

    async def notify_speech_end(self) -> None:
        """Sends client-side Hybrid VAD signal when silence/turn-end is detected."""
        if self.is_connected and self._session:
            await self._session.send_realtime_input(audio_stream_end=True)

    async def receive_events(self) -> AsyncGenerator[TranscribeEvent, None]:
        """Yields streaming transcription events (interim hypotheses and finalized text)."""
        if not self.is_connected or not self._session:
            raise RuntimeError("Transcriber session is not active")

        try:
            async for response in self._session.receive():
                content = getattr(response, "server_content", None)
                if not content:
                    continue

                # 1. Interim streaming transcription
                interim = getattr(content, "interim_input_transcription", None)
                if interim and getattr(interim, "text", None):
                    yield TranscribeEvent(
                        text=interim.text,
                        is_interim=True,
                        is_final=False,
                    )

                # 2. Finalized transcription
                final = getattr(content, "input_transcription", None)
                if final and getattr(final, "text", None):
                    yield TranscribeEvent(
                        text=final.text,
                        is_interim=False,
                        is_final=True,
                    )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Error in transcription receive loop: %s", exc)

    async def close(self) -> None:
        """Gracefully closes the transcription session."""
        self.is_connected = False
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
        logger.info("Closed %s transcription session", self.model)
