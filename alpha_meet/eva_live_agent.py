"""Embedded LiveKit participant that gives Eva real Gemini Live audio."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from google.genai import types
from livekit import rtc
from livekit.agents import Agent, AgentSession, room_io
from livekit.plugins import google

from alpha_core.config import settings
from alpha_meet.tokens import LiveKitTokenGenerator
from alpha_meet.transcribe_agent import TranscribeAgent
from alpha_meet.translate_agent import TranslateAgent

logger = logging.getLogger("alpha_meet.eva_live_agent")
EVA_IDENTITY = "eva-cto"
EVA_LINKED_PARTICIPANT_ATTRIBUTE = "alpha.eva.linkedParticipant"
EVA_TARGET_TOPIC = "alpha.eva.target"

EVA_LIVE_INSTRUCTIONS = """
You are Eva, the Lead Engineering CTO and AI Architect at DeployMate, in a live technical meeting with Ajay (Founder/CEO) and the Client.

Language Rules (CRITICAL):
- When Ajay or any participant speaks to you in Hindi (or Hinglish), you MUST reply fluently and naturally in Hindi (or professional conversational Hinglish) as CTO. Never respond in English when spoken to in Hindi.
- If a client speaks in English, respond in English. If a client speaks another language (e.g. Chinese, Spanish), match their language.
- Speak with natural, confident technical executive cadence: authoritative, articulate, warm, and highly competent.
- Strict Documentation Rule: While speaking in Hindi/Hinglish during the meeting, ALL formal technical notes, task graphs, architecture blueprints, and database records you generate for AlphaBrain must be in clean, professional English.

CTO Guidance & Capabilities:
- Deep expertise across full-stack architecture, FastAPI, Go microservices, LiveKit WebRTC, PostgreSQL, Supabase, Redis, and AI systems.
- Provide crisp, high-signal 2-3 sentence answers with clear architectural trade-offs.
- When requirements are ambiguous, ask one sharp, clarifying question.
- Do not repeat greetings. If interrupted, stop immediately and listen.
""".strip()


@dataclass
class EvaRoomRuntime:
    room_name: str
    state: str = "starting"
    error: str | None = None
    active_speaker: str | None = None
    human_participants: set[str] = field(default_factory=set)
    participant_languages: dict[str, str] = field(default_factory=dict)
    translate_agents: dict[str, TranslateAgent] = field(default_factory=dict)
    transcribe_agent: TranscribeAgent | None = None
    translate_mode: str = "transcribe_only"
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None

    def public_status(self) -> dict[str, Any]:
        return {
            "identity": EVA_IDENTITY,
            "room_name": self.room_name,
            "state": self.state,
            "voice": settings.GEMINI_LIVE_VOICE,
            "model": settings.GEMINI_LIVE_MODEL,
            "active_speaker": self.active_speaker,
            "human_participants": len(self.human_participants),
            "languages": sorted(
                {
                    language
                    for identity, language in self.participant_languages.items()
                    if identity in self.human_participants
                }
            ),
            "translate_mode": self.translate_mode,
            "error": self.error,
        }


class EvaRoomManager:
    """Own one shared-context Eva participant per LiveKit room."""

    def __init__(self) -> None:
        self._rooms: dict[str, EvaRoomRuntime] = {}
        self._lock = asyncio.Lock()
        self._bg_tasks: set[asyncio.Task[Any]] = set()

    async def ensure_room(
        self,
        room_name: str,
        language: str = "en",
        identity: str = "",
        timeout_seconds: float = 15.0,
    ) -> dict[str, Any]:
        self._validate_configuration()
        async with self._lock:
            runtime = self._rooms.get(room_name)
            if runtime is None or runtime.task is None or runtime.task.done():
                runtime = EvaRoomRuntime(room_name=room_name)
                runtime.task = asyncio.create_task(
                    self._run_room(runtime),
                    name=f"eva-live-{room_name}",
                )
                self._rooms[room_name] = runtime

            if identity and language:
                runtime.participant_languages[identity] = language
                task = asyncio.create_task(self._reconcile_translate_agents(runtime))
                self._bg_tasks.add(task)
                task.add_done_callback(self._bg_tasks.discard)

        try:
            await asyncio.wait_for(runtime.ready.wait(), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise RuntimeError("Eva did not become ready before timeout") from exc
        if runtime.error:
            raise RuntimeError(runtime.error)
        return runtime.public_status()

    def status(self, room_name: str) -> dict[str, Any]:
        runtime = self._rooms.get(room_name)
        if runtime is None:
            return {
                "identity": EVA_IDENTITY,
                "room_name": room_name,
                "state": "not_started",
            }
        return runtime.public_status()

    async def stop_all(self) -> None:
        runtimes = list(self._rooms.values())
        for runtime in runtimes:
            runtime.stop.set()
        tasks = [runtime.task for runtime in runtimes if runtime.task is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _validate_configuration() -> None:
        if settings.GEMINI_USE_VERTEX and not settings.GOOGLE_CLOUD_PROJECT:
            raise RuntimeError("Vertex AI project is not configured")
        if not settings.GEMINI_USE_VERTEX and not (settings.EVA_GEMINI_LIVE_API_KEY or settings.GEMINI_LIVE_API_KEY or settings.GOOGLE_API_KEY):
            raise RuntimeError("Gemini Live API key is not configured")
        if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
            raise RuntimeError("LiveKit credentials are not configured")
        if not settings.LIVEKIT_URL:
            raise RuntimeError("LiveKit URL is not configured")

    async def _reconcile_translate_agents(self, runtime: EvaRoomRuntime) -> None:
        """Spawns or tears down TranslateAgents based on participant languages."""
        if not settings.TRANSLATE_ENABLED:
            return

        async with self._lock:
            active_identities = runtime.human_participants
            # Only count languages for currently active human participants
            active_langs = {
                language
                for identity, language in runtime.participant_languages.items()
                if identity in active_identities
            }

            if len(active_langs) <= 1:
                runtime.translate_mode = "transcribe_only"
                # Tear down all translate agents
                for agent in list(runtime.translate_agents.values()):
                    await agent.stop()
                runtime.translate_agents.clear()

                # Ensure dedicated Gemini 3.5 Transcribe Live agent is active
                if settings.TRANSCRIBE_ENABLED and runtime.transcribe_agent is None:
                    transcriber = TranscribeAgent(room_name=runtime.room_name)
                    runtime.transcribe_agent = transcriber
                    await transcriber.start()
            else:
                runtime.translate_mode = "live_translate"
                if runtime.transcribe_agent is not None:
                    await runtime.transcribe_agent.stop()
                    runtime.transcribe_agent = None

                # Start missing agents
                for lang in active_langs:
                    if lang not in runtime.translate_agents:
                        agent = TranslateAgent(room_name=runtime.room_name, target_language=lang)
                        runtime.translate_agents[lang] = agent
                        await agent.start()

                # Stop unneeded agents
                unneeded_langs = set(runtime.translate_agents.keys()) - active_langs
                for lang in unneeded_langs:
                    agent = runtime.translate_agents.pop(lang)
                    await agent.stop()

    @staticmethod
    def _model_options() -> dict[str, Any]:
        live_model = getattr(settings, "EVA_GEMINI_LIVE_MODEL", None) or settings.GEMINI_LIVE_MODEL
        options: dict[str, Any] = {
            "model": live_model,
            "voice": settings.GEMINI_LIVE_VOICE,
            "instructions": EVA_LIVE_INSTRUCTIONS,
            "input_audio_transcription": types.AudioTranscriptionConfig(),
            "output_audio_transcription": types.AudioTranscriptionConfig(),
            "temperature": 0.6,
            "session_resumption": types.SessionResumptionConfig(transparent=True),
            "context_window_compression": types.ContextWindowCompressionConfig(
                trigger_tokens=24_000,
                sliding_window=types.SlidingWindow(target_tokens=12_000),
            ),
        }
        # Gemini 3.x Live models do not support affective dialog or proactivity flags
        if not ("gemini-3" in live_model or "gemini-live-3" in live_model):
            options["enable_affective_dialog"] = True
            options["proactivity"] = True
        if settings.GEMINI_USE_VERTEX:
            options.update(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION,
            )
        else:
            options["api_key"] = (
                settings.EVA_GEMINI_LIVE_API_KEY
                or settings.GEMINI_LIVE_API_KEY
                or settings.GOOGLE_API_KEY
            )
        return options

    @staticmethod
    async def _wait_for_provider_connection(
        model: google.realtime.RealtimeModel,
        failed: asyncio.Event,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Wait until LiveKit's Gemini adapter owns a connected provider session."""
        try:
            async with asyncio.timeout(timeout_seconds):
                while not failed.is_set():
                    sessions = tuple(getattr(model, "_sessions", ()))
                    if any(getattr(item, "_active_session", None) is not None for item in sessions):
                        return
                    await asyncio.sleep(0.05)
        except TimeoutError as exc:
            raise RuntimeError("Gemini Live provider connection timed out") from exc
        raise RuntimeError("Gemini Live provider connection failed")

    async def _run_room(self, runtime: EvaRoomRuntime) -> None:
        room = rtc.Room()
        session: AgentSession | None = None
        provider_failed = asyncio.Event()
        initial_join_timeout: asyncio.Task[None] | None = None
        empty_room_timeout: asyncio.Task[None] | None = None

        async def publish_linked_participant(identity: str) -> None:
            try:
                await room.local_participant.set_attributes(
                    {EVA_LINKED_PARTICIPANT_ATTRIBUTE: identity}
                )
            except Exception:
                logger.exception("Could not publish Eva participant link for %s", identity)

        _bg_tasks: set[asyncio.Task[Any]] = set()

        def choose_participant(identity: str) -> None:
            runtime.active_speaker = identity
            linked_room_io = getattr(session, "_room_io", None)
            if linked_room_io is not None:
                linked_room_io.set_participant(identity)
                task = asyncio.create_task(publish_linked_participant(identity))
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)

        def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            nonlocal initial_join_timeout, empty_room_timeout
            if participant.identity.startswith("translate-") or participant.identity.startswith("transcriber-"):
                return
            runtime.human_participants.add(participant.identity)
            task = asyncio.create_task(self._reconcile_translate_agents(runtime))
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

            if initial_join_timeout is not None:
                initial_join_timeout.cancel()
                initial_join_timeout = None
            if empty_room_timeout is not None:
                empty_room_timeout.cancel()
                empty_room_timeout = None
            if runtime.active_speaker is None:
                choose_participant(participant.identity)

        def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            nonlocal empty_room_timeout
            if participant.identity.startswith("translate-") or participant.identity.startswith("transcriber-"):
                return
            runtime.human_participants.discard(participant.identity)
            task = asyncio.create_task(self._reconcile_translate_agents(runtime))
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)
            if runtime.active_speaker == participant.identity:
                runtime.active_speaker = next(iter(runtime.human_participants), None)
                if runtime.active_speaker:
                    choose_participant(runtime.active_speaker)
            if not runtime.human_participants:
                empty_room_timeout = asyncio.create_task(stop_after(20.0))

        def on_active_speakers_changed(participants: list[rtc.Participant]) -> None:
            for participant in participants:
                if participant.identity in runtime.human_participants:
                    choose_participant(participant.identity)
                    break

        def on_data_received(packet: rtc.DataPacket) -> None:
            participant = packet.participant
            if (
                packet.topic == EVA_TARGET_TOPIC
                and participant is not None
                and participant.identity in runtime.human_participants
            ):
                choose_participant(participant.identity)

        async def stop_after(delay_seconds: float) -> None:
            await asyncio.sleep(delay_seconds)
            if not runtime.human_participants:
                runtime.stop.set()

        try:
            room.on("participant_connected", on_participant_connected)
            room.on("participant_disconnected", on_participant_disconnected)
            room.on("active_speakers_changed", on_active_speakers_changed)
            room.on("data_received", on_data_received)
            room.on("disconnected", lambda *_: runtime.stop.set())

            eva_token = LiveKitTokenGenerator().generate_token(
                room_name=runtime.room_name,
                participant_identity=EVA_IDENTITY,
                participant_name="Eva (DeployMate CTO)",
                role="eva",
                valid_minutes=30,
            )
            await room.connect(settings.LIVEKIT_URL, eva_token)

            model = google.realtime.RealtimeModel(**self._model_options())
            session = AgentSession(
                llm=model,
                turn_handling={"interruption": {"enabled": True}},
            )

            @session.on("agent_state_changed")
            def on_agent_state_changed(event: Any) -> None:
                runtime.state = event.new_state

            @session.on("error")
            def on_session_error(event: Any) -> None:
                logger.error("Eva Gemini Live session error: %s", event.error)
                runtime.state = "failed"
                runtime.error = "Gemini Live session failed"
                provider_failed.set()
                runtime.ready.set()
                runtime.stop.set()

            @session.on("close")
            def on_session_close(event: Any) -> None:
                if getattr(event, "error", None) and runtime.error is None:
                    runtime.state = "failed"
                    runtime.error = "Gemini Live session closed with an error"
                    provider_failed.set()
                    runtime.ready.set()
                runtime.stop.set()

            await session.start(
                agent=Agent(instructions=EVA_LIVE_INSTRUCTIONS, id="eva-cto"),
                room=room,
                room_options=room_io.RoomOptions(
                    audio_input=True,
                    video_input=True,
                    audio_output=True,
                    text_input=True,
                    text_output=True,
                    close_on_disconnect=False,
                ),
                record=False,
            )
            await self._wait_for_provider_connection(model, provider_failed)
            if runtime.active_speaker:
                choose_participant(runtime.active_speaker)
            runtime.state = "ready"
            runtime.ready.set()
            initial_join_timeout = asyncio.create_task(stop_after(60.0))
            await runtime.stop.wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            runtime.state = "failed"
            runtime.error = str(exc)
            logger.exception("Eva failed to join LiveKit room %s", runtime.room_name)
            runtime.ready.set()
        finally:
            for timeout_task in (initial_join_timeout, empty_room_timeout):
                if timeout_task is not None:
                    timeout_task.cancel()
            if session is not None:
                try:
                    await asyncio.wait_for(session.aclose(), timeout=10.0)
                except TimeoutError:
                    logger.warning("Timed out closing Eva session for %s", runtime.room_name)
            if runtime.transcribe_agent is not None:
                try:
                    await runtime.transcribe_agent.stop()
                except Exception:
                    pass
                runtime.transcribe_agent = None
            if room.isconnected():
                await room.disconnect()
            if runtime.state != "failed":
                runtime.state = "stopped"
            runtime.ready.set()


eva_room_manager = EvaRoomManager()
