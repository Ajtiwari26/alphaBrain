import asyncio
import base64
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit
from xml.sax.saxutils import escape as xml_escape

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.commentary import LiveCommentaryEngine
from alpha_core.config import settings
from alpha_core.db.connection import get_db_session, get_session_factory, init_db
from alpha_core.db.models import (
    ApprovalRecord,
    AttemptRecord,
    AuditEventRecord,
    ProjectRecord,
    TaskRecord,
    WorkerHealthRecord,
    WorkerRecord,
    utc_now,
)
from alpha_core.queue.triage_queue import (
    EmergencyStopActiveError,
    TaskTriageQueue,
    TriageStatus,
)
from alpha_core.safety.gate import SafetyGate
from alpha_core.security import (
    AuthPrincipal,
    PrincipalRole,
    create_meeting_invite,
    create_scoped_stream_token,
    create_worker_identity_token,
    plivo_nonce_cache,
    redact_dict,
    redact_secrets,
    require_api_principal,
    require_permission,
    require_project_access,
    require_worker_bootstrap_principal,
    require_worker_principal,
    validate_plivo_v3_signature,
    verify_meeting_invite,
    verify_scoped_stream_token,
    verify_websocket_bearer,
    worker_kill_switch,
)
from alpha_core.self_development import SelfImprovementRequest, create_self_improvement_task
from alpha_core.state.spec_engine import SpecEngine, TaskGraphPlanningConstraints
from alpha_core.state.task_engine import TaskEngine
from alpha_meet.eva_agent import EvaMeetingAgent
from alpha_meet.eva_live_agent import eva_room_manager
from alpha_meet.live_audio import LiveMeetAudioBridge
from alpha_meet.tokens import LiveKitTokenGenerator, MeetingRole
from alpha_protocol import (
    AcceptancePlan,
    ApprovalStatus,
    CallJob,
    PersonaType,
    PromotionRequest,
    PromotionResult,
    SpecVersion,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    WorkerHealthReport,
    WorkerRegistration,
    compute_promotion_digest,
)
from alpha_voice.extractor import SpecExtractor
from alpha_voice.plivo_bridge import PlivoVoiceBridge

MEET_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "alpha_meet" / "frontend"
PORTAL_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "alpha_portal"
eva_meet_agent = EvaMeetingAgent()
live_commentary_engine = LiveCommentaryEngine()
logger = logging.getLogger("alpha_core.api")
SAFE_EXTERNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_LANGUAGE_CODE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class SelfDevelopmentTaskSubmission(BaseModel):
    """Founder request to queue one bounded AlphaBrain self-development task."""

    task_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(default="prj_alphabrain_self", min_length=1, max_length=64)
    source_repo: Path
    allowed_paths: list[str] = Field(min_length=1)
    objective: str = Field(min_length=1, max_length=2000)
    detailed_instructions: str | None = Field(default=None, max_length=20000)
    base_commit: str = Field(default="HEAD", min_length=1, max_length=128)
    acceptance_plan: AcceptancePlan


class TaskCancellationRequest(BaseModel):
    """Founder cancellation reason persisted in task audit history."""

    reason: str = Field(min_length=1, max_length=2000)


class ProjectRegistrationRequest(BaseModel):
    """Founder-owned binding between control-plane project and Mac repository."""

    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    name: str = Field(min_length=1, max_length=255)
    repo_path: str = Field(min_length=1, max_length=512)


class TaskGraphSubmissionRequest(BaseModel):
    """Founder-authored frozen task graph for one registered project."""

    tasks: list[TaskEnvelope] = Field(min_length=1, max_length=50)


class SpecApprovalDecisionRequest(BaseModel):
    """Founder decision bound to exact immutable specification digest."""

    approved: bool
    scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str | None = Field(default=None, max_length=2000)


def _validate_repo_reference(repo_path: str) -> str:
    """Validate repo syntax and configured-root binding without touching Render disk."""
    if any(ord(character) < 32 for character in repo_path):
        raise ValueError("Repository reference contains control characters")
    path = PurePosixPath(repo_path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Repository reference must be an absolute path without traversal")
    if str(path) != repo_path:
        raise ValueError("Repository reference must use canonical POSIX path syntax")
    allowed_roots = tuple(
        PurePosixPath(str(root.expanduser())) for root in settings.ALLOWED_REPO_ROOTS
    )
    if not allowed_roots:
        raise ValueError("No repository roots are configured")
    if not any(path == root or path.is_relative_to(root) for root in allowed_roots):
        raise ValueError("Repository reference is outside allowed roots")
    return repo_path


async def watchdog_scheduler():
    session_factory = get_session_factory()
    while True:
        try:
            async with session_factory() as session:
                await TaskEngine.timeout_expired_leases(session)
                await TaskEngine.check_watchdog_stalls(
                    session, stall_timeout_seconds=settings.TASK_PROGRESS_STALL_TIMEOUT_SECONDS
                )
                await TaskEngine.release_due_retries(session)
                await session.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Watchdog scheduler failed: {e.__class__.__name__} - {e}")
        try:
            await asyncio.sleep(settings.TASK_WATCHDOG_SCAN_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await init_db()
    watchdog_task = asyncio.create_task(watchdog_scheduler())
    try:
        yield
    finally:
        watchdog_task.cancel()
        with suppress(asyncio.CancelledError):
            await watchdog_task
        await eva_room_manager.stop_all()


app = FastAPI(
    title="Alpha Brain Master API",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow only explicitly configured local or deployed web origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEETING_CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "connect-src 'self' ws: wss:",
    )
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = MEETING_CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(self), microphone=(self), display-capture=(self)"
    )
    return response


if MEET_FRONTEND_DIR.exists():
    app.mount("/static/meet", StaticFiles(directory=str(MEET_FRONTEND_DIR)), name="static_meet")

if PORTAL_FRONTEND_DIR.exists():
    app.mount(
        "/portal", StaticFiles(directory=str(PORTAL_FRONTEND_DIR), html=True), name="static_portal"
    )


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.ENV,
    }


@app.get("/health/live")
async def liveness_check():
    """Liveness proves process event loop responds."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_check():
    """Readiness proves database connection and migration compatibility."""
    try:
        from sqlalchemy import text

        from alpha_core.db.connection import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. Check database connection
            await session.execute(text("SELECT 1"))

            # 2. Check exact schema compatibility
            res = await session.execute(text("SELECT version_num FROM alembic_version"))
            rows = res.scalars().all()

            if not rows:
                raise ValueError("Empty migration history")
            if len(rows) > 1:
                raise ValueError("Multiple migration heads found")
            if rows[0] != settings.EXPECTED_ALEMBIC_REVISION:
                raise ValueError("Migration revision mismatch")

        return {"status": "ready"}
    except Exception:
        logger.error("Readiness check failed")
        raise HTTPException(status_code=503, detail="Service Unavailable") from None


@app.post("/api/workers/{worker_id}/identity")
async def issue_worker_identity(
    worker_id: str,
    principal: AuthPrincipal = Depends(require_worker_bootstrap_principal),
):
    if not SAFE_EXTERNAL_ID.fullmatch(worker_id):
        raise HTTPException(status_code=422, detail="Invalid worker ID")

    # Issue identity token valid for 1 hour (3600 seconds)
    ttl_seconds = 3600
    token = create_worker_identity_token(worker_id, ttl_seconds=ttl_seconds)
    expires_at = int(time.time()) + ttl_seconds

    return {
        "identity_token": token,
        "expires_at": expires_at,
    }


@app.post("/api/workers/register")
async def register_worker(
    registration: WorkerRegistration,
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if registration.worker_id != principal.subject:
        raise HTTPException(status_code=403, detail="Worker ID does not match authenticated worker")
    worker = await TaskEngine.register_worker(session, registration)
    return {"status": "registered", "worker_id": worker.id}


@app.post("/api/workers/{worker_id}/health")
async def record_worker_health(
    worker_id: str,
    report: WorkerHealthReport,
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if worker_id != principal.subject or report.worker_id != principal.subject:
        raise HTTPException(status_code=403, detail="Worker ID does not match authenticated worker")
    worker = await TaskEngine.record_worker_health(session, report)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker must register before reporting health")
    return {"status": "recorded", "worker_id": worker.id, "worker_status": worker.status}


@app.get("/api/workers/{worker_id}")
async def get_worker_status(
    worker_id: str,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "worker:read")
    worker = await session.get(WorkerRecord, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    latest = await session.scalar(
        select(WorkerHealthRecord)
        .where(WorkerHealthRecord.worker_id == worker_id)
        .order_by(WorkerHealthRecord.reported_at.desc())
        .limit(1)
    )
    return {
        "worker_id": worker.id,
        "hostname": worker.hostname,
        "platform": worker.platform,
        "status": worker.status,
        "last_heartbeat_at": (
            worker.last_heartbeat_at.isoformat() if worker.last_heartbeat_at else None
        ),
        "latest_health": {
            "battery_percent": latest.battery_percent,
            "ac_power": latest.ac_power,
            "thermal_pressure": latest.thermal_pressure,
            "active_task_count": latest.active_task_count,
            "reported_at": latest.reported_at.isoformat() if latest.reported_at else None,
        }
        if latest
        else None,
    }


# ==========================================
# Meeting Room (You + Client + Eva) Endpoints
# ==========================================


@app.get("/meet", response_class=HTMLResponse)
async def get_meeting_room():
    """Serves the 3-Way LiveKit WebRTC meeting room."""
    index_file = MEET_FRONTEND_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Meeting frontend not found")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.post("/api/meet/token")
async def generate_meet_token(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    """Generates a signed LiveKit WebRTC access token."""
    invite_token = payload.get("invite_token")
    invite_claims = verify_meeting_invite(invite_token) if invite_token else None
    if invite_token and invite_claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired meeting invite")

    if invite_claims:
        room_name = invite_claims["room"]
        identity = invite_claims["identity"]
        role = invite_claims["role"]
    else:
        require_api_principal(authorization)
        room_name = payload.get("room_name", "deploymate-main")
        identity = payload.get("identity", "Ajay (Founder)")
        role = "founder"

    if not isinstance(room_name, str) or not SAFE_EXTERNAL_ID.fullmatch(room_name):
        raise HTTPException(status_code=422, detail="Invalid room name")
    if not isinstance(identity, str) or not identity.strip() or len(identity) > 128:
        raise HTTPException(status_code=422, detail="Invalid participant identity")
    if role not in {"founder", "client"}:
        raise HTTPException(status_code=403, detail="Meeting role is not allowed")
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(status_code=503, detail="LiveKit credentials are not configured")

    try:
        language = payload.get("language", "hi")
        eva_status = await eva_room_manager.ensure_room(
            room_name, language=language, identity=identity
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    token = LiveKitTokenGenerator().generate_token(
        room_name=room_name,
        participant_identity=identity,
        role=cast(MeetingRole, role),
    )
    return {
        "token": token,
        "room_name": room_name,
        "identity": identity,
        "role": role,
        "livekit_url": settings.LIVEKIT_URL,
        "eva": eva_status,
    }


@app.post("/api/meet/invite")
async def generate_meet_invite(
    payload: dict[str, Any],
    _principal: AuthPrincipal = Depends(require_api_principal),
):
    """Create short-lived client link without exposing Alpha Brain API token."""
    require_permission(_principal, "meeting:invite")
    room_name = payload.get("room_name", "deploymate-main")
    identity = payload.get("identity", "Client")
    if not isinstance(room_name, str) or not SAFE_EXTERNAL_ID.fullmatch(room_name):
        raise HTTPException(status_code=422, detail="Invalid room name")
    if not isinstance(identity, str) or not identity.strip() or len(identity) > 128:
        raise HTTPException(status_code=422, detail="Invalid participant identity")

    invite = create_meeting_invite(
        room_name=room_name,
        identity=identity.strip(),
        role="client",
        ttl_seconds=3600,
    )
    join_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/meet#invite={quote(invite, safe='')}"
    return {
        "expires_in_seconds": 3600,
        "identity": identity.strip(),
        "join_url": join_url,
        "room_name": room_name,
    }


@app.get("/api/meet/status/{room_name}")
async def get_meet_status(
    room_name: str,
    _principal: AuthPrincipal = Depends(require_api_principal),
):
    if not SAFE_EXTERNAL_ID.fullmatch(room_name):
        raise HTTPException(status_code=422, detail="Invalid room name")
    return {"eva": eva_room_manager.status(room_name)}


@app.get("/api/meet/slide")
async def get_meet_slide(
    project: str = "alphaBrain",
    _principal: AuthPrincipal = Depends(require_api_principal),
):
    """Returns dynamic architecture slide presentation for Eva's Screen Share."""
    require_permission(_principal, "project:read")
    require_project_access(_principal, project)
    slide = eva_meet_agent.generate_presentation_slide(project_name=project)
    return JSONResponse(slide)


class TranslateTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    target_language: str = Field(default="en", max_length=10)
    invite_token: str | None = Field(default=None, max_length=4096)


@app.post("/api/meet/translate-text")
async def translate_meet_text(
    payload: TranslateTextRequest,
    authorization: str | None = Header(default=None),
):
    """Translates speech transcript segments to clear English for live dual-language notes."""
    if payload.invite_token:
        if verify_meeting_invite(payload.invite_token) is None:
            raise HTTPException(status_code=401, detail="Invalid or expired meeting invite")
    else:
        require_api_principal(authorization)

    text = payload.text.strip()
    if not text:
        return {"translated_text": "", "is_translated": False}
    target_language = payload.target_language.strip()
    if not SAFE_LANGUAGE_CODE.fullmatch(target_language):
        raise HTTPException(status_code=422, detail="Invalid target language")

    # If text is purely ASCII alphanumeric/punctuation and likely English, skip translation
    if target_language.lower().startswith("en") and all(ord(c) < 128 for c in text):
        words = text.split()
        if words and not any(
            word.lower() in {"namaste", "matlab", "kya", "hai", "nahi", "accha", "theek"}
            for word in words
        ):
            return {"translated_text": text, "is_translated": False}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.1-flash-lite-preview",
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a real-time meeting translator for AlphaBrain. "
                    f"Translate the transcript into concise, natural language code {target_language}. "
                    "Preserve software engineering terms accurately. "
                    "Output only translated text. No notes, explanations, or quotes."
                ),
                temperature=0.2,
            ),
        )
        translated = (response.text or "").strip()
        is_diff = bool(translated and translated.lower() != text.lower())
        return {"translated_text": translated if is_diff else text, "is_translated": is_diff}
    except Exception as exc:
        logger.warning("Could not translate transcript text: %s", exc)
        return {"translated_text": text, "is_translated": False}


@app.post("/api/meet/speak")
async def meet_speak(
    payload: dict[str, str],
    _principal: AuthPrincipal = Depends(require_api_principal),
):
    """Processes spoken input and generates Eva's CTO voice reply."""
    require_permission(_principal, "meeting:join")
    speaker = payload.get("speaker", "Participant")
    text = payload.get("text", "")

    eva_meet_agent.append_turn(speaker, text)

    eva_reply = eva_meet_agent.generate_response(speaker, text)
    eva_meet_agent.append_turn("Eva (CTO)", eva_reply)

    return {
        "status": "success",
        "eva_reply": eva_reply,
        "transcript": eva_meet_agent.transcript_history,
    }


@app.websocket("/ws/meet/live-audio")
async def meet_live_audio_websocket(websocket: WebSocket, persona: str = "eva"):
    """Live duplex audio WebSocket stream connecting browser mic with Gemini Live."""
    if not verify_websocket_bearer(
        websocket.query_params.get("access_token"),
        settings.ALPHA_API_TOKEN,
    ):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    bridge = LiveMeetAudioBridge(websocket=websocket, persona=persona)
    try:
        await bridge.run()
    except WebSocketDisconnect:
        logger.info("Live audio WebSocket disconnected")
    except Exception as exc:
        logger.warning("Live audio WebSocket failed: %s", redact_secrets(str(exc)))


# ==========================================
# Task Management Endpoints
# ==========================================


@app.post("/api/projects", response_model=dict[str, Any])
async def register_project(
    payload: ProjectRegistrationRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Register immutable project-to-repository binding for outbound Mac workers."""
    require_permission(principal, "project:write")
    require_project_access(principal, payload.project_id)
    existing: ProjectRecord | None = None
    try:
        repo_path = _validate_repo_reference(payload.repo_path)
        existing = await session.get(ProjectRecord, payload.project_id)
        project = await TaskEngine.create_project(
            session,
            project_id=payload.project_id,
            name=payload.name,
            repo_path=repo_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409 if existing else 422, detail=str(exc)) from exc
    return {
        "status": "existing" if existing else "registered",
        "project_id": project.id,
        "name": project.name,
        "repo_path": project.repo_path,
    }


@app.post("/api/projects/{project_id}/specs", response_model=dict[str, Any])
async def submit_project_specification(
    project_id: str,
    spec: SpecVersion,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Persist one immutable pending specification version for founder review."""
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=403, detail="Specification submission requires founder access"
        )
    require_permission(principal, "spec:write")
    require_project_access(principal, project_id)
    if spec.project_id != project_id:
        raise HTTPException(status_code=422, detail="Specification project does not match URL")
    try:
        record, digest = await SpecEngine.submit_spec(session, spec, actor=principal.subject)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "status": record.status,
        "project_id": record.project_id,
        "spec_id": record.id,
        "version": record.version,
        "scope_sha256": digest,
    }


@app.post("/api/projects/{project_id}/specs/{spec_id}/approval", response_model=dict[str, Any])
async def decide_project_specification(
    project_id: str,
    spec_id: str,
    payload: SpecApprovalDecisionRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Record founder decision against exact pending specification digest."""
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=403, detail="Specification approval requires founder access"
        )
    require_permission(principal, "spec:approve")
    require_project_access(principal, project_id)
    try:
        record = await SpecEngine.decide_founder_approval(
            session,
            spec_id,
            approved=payload.approved,
            actor=principal.subject,
            scope_sha256=payload.scope_sha256,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Specification not found in project")
    return {
        "status": record.status,
        "project_id": record.project_id,
        "spec_id": record.id,
        "version": record.version,
        "founder_approved": bool(record.founder_approved),
    }


@app.post(
    "/api/projects/{project_id}/specs/{spec_id}/task-graph-draft",
    response_model=dict[str, Any],
)
async def draft_specification_task_graph(
    project_id: str,
    spec_id: str,
    constraints: TaskGraphPlanningConstraints,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Draft deterministic non-executable task packets from one approved spec."""
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Task planning requires founder access")
    require_permission(principal, "task:write")
    require_project_access(principal, project_id)
    try:
        draft = await SpecEngine.draft_task_graph(session, spec_id, constraints)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if draft.project_id != project_id:
        raise HTTPException(status_code=404, detail="Specification not found in project")
    return cast(dict[str, Any], draft.model_dump(mode="json"))


@app.post("/api/tasks", response_model=dict[str, Any])
async def submit_task(
    envelope: TaskEnvelope,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:write")
    require_project_access(_principal, envelope.project_id)
    if not worker_kill_switch.can_execute(envelope.project_id):
        raise HTTPException(status_code=403, detail="Task execution is paused for this project")
    try:
        _validate_repo_reference(envelope.repo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    project = await session.get(ProjectRecord, envelope.project_id)
    if project is None and (settings.is_staging or settings.is_production):
        raise HTTPException(
            status_code=404,
            detail="Project must be registered before submitting remote tasks",
        )
    if project is not None and project.repo_path != envelope.repo:
        raise HTTPException(
            status_code=409,
            detail="Task repository does not match registered project binding",
        )
    try:
        task = await TaskEngine.submit_task(session, envelope)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": task.status, "task_id": task.id, "project_id": task.project_id}


@app.post("/api/projects/{project_id}/task-graph", response_model=dict[str, Any])
async def submit_task_graph(
    project_id: str,
    payload: TaskGraphSubmissionRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Validate and atomically queue one project task DAG."""
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Task graph submission requires founder access")
    require_permission(principal, "task:write")
    require_project_access(principal, project_id)
    if not SAFE_EXTERNAL_ID.fullmatch(project_id):
        raise HTTPException(status_code=422, detail="Invalid project ID")
    if not worker_kill_switch.can_execute(project_id):
        raise HTTPException(status_code=403, detail="Task execution is paused for this project")

    project = await session.get(ProjectRecord, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project must be registered first")
    for envelope in payload.tasks:
        try:
            _validate_repo_reference(envelope.repo)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        tasks = await TaskEngine.submit_task_graph(
            session,
            payload.tasks,
            project_id=project_id,
            actor=principal.subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "status": "accepted",
        "project_id": project_id,
        "tasks": [
            {
                "task_id": task.id,
                "status": task.status,
                "packet_sha256": task.packet_sha256,
                "depends_on": task.depends_on_json or [],
            }
            for task in tasks
        ],
    }


@app.post("/api/self-development/tasks", response_model=dict[str, Any])
async def submit_self_development_task(
    payload: SelfDevelopmentTaskSubmission,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Queue founder-approved self-work; execution remains separately approved."""

    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Self-development requires founder access")
    require_permission(principal, "task:write")
    require_project_access(principal, payload.project_id)
    if not worker_kill_switch.can_execute(payload.project_id):
        raise HTTPException(status_code=403, detail="Task execution is paused for this project")

    request = SelfImprovementRequest(
        source_repo=payload.source_repo,
        allowed_paths=tuple(payload.allowed_paths),
        founder_identity=principal.subject,
        requires_approval=True,
        base_commit=payload.base_commit,
    )
    try:
        task = await create_self_improvement_task(
            session,
            request,
            project_id=payload.project_id,
            task_id=payload.task_id,
            objective=payload.objective,
            detailed_instructions=payload.detailed_instructions,
            acceptance_plan=payload.acceptance_plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": task.status,
        "task_id": task.id,
        "project_id": task.project_id,
        "packet_sha256": task.packet_sha256,
        "execution_started": False,
        "next_owner_action": "founder_approval_required",
    }


@app.post("/api/tasks/lease")
async def lease_task(
    payload: dict[str, str],
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(principal, "task:read")
    if not worker_kill_switch.can_execute():
        return {"status": "no_tasks_available"}
    worker_id = payload.get("worker_id", principal.subject)
    if worker_id != principal.subject:
        raise HTTPException(status_code=403, detail="Worker ID does not match authenticated worker")
    if not SAFE_EXTERNAL_ID.fullmatch(worker_id):
        raise HTTPException(status_code=422, detail="Invalid worker ID")
    preferred_agent = payload.get("preferred_agent")

    allowed_project_ids = list(principal.project_ids) if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN} else None
    leased_tuple = await TaskEngine.lease_next_task(
        session,
        worker_id,
        preferred_agent=preferred_agent,
        lease_duration_seconds=settings.WORKER_LEASE_DURATION_SECONDS,
        project_ids=allowed_project_ids
    )

    await session.commit()

    if not leased_tuple:
        return {"status": "no_tasks_available"}

    task_record, envelope = leased_tuple

    return {
        "status": "leased",
        "lease_token": task_record.lease_token,
        "task": envelope.model_dump(),
    }


@app.post("/api/tasks/{task_id}/heartbeat")
async def task_heartbeat(
    task_id: str,
    payload: dict[str, str],
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(principal, "task:write")
    lease_token = payload.get("lease_token", "")
    # Enforce multi-tenant boundaries
    task = await session.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(principal, task.project_id)
    success = await TaskEngine.record_heartbeat(session, task_id, lease_token, principal.subject)
    if not success:
        if (
            task
            and task.status == TaskStatus.CANCELLED.value
            and task.worker_id == principal.subject
            and task.lease_token == lease_token
        ):
            return {"status": "cancel_requested"}
        raise HTTPException(status_code=400, detail="Invalid lease token or task not found")
    return {"status": "heartbeat_recorded"}


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task_execution(
    task_id: str,
    payload: TaskCancellationRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Cancel queued or active task and signal its authenticated worker."""

    require_permission(principal, "task:cancel")
    task = await session.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(principal, task.project_id)
    try:
        cancelled = await TaskEngine.cancel_task(
            session,
            task_id,
            reason=payload.reason,
            actor=principal.subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not cancelled:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": "cancel_requested",
        "task_id": task_id,
        "worker_signal_pending": task.worker_id is not None,
    }


@app.post("/api/tasks/{task_id}/result")
async def submit_task_result(
    task_id: str,
    payload: dict[str, Any],
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(principal, "task:write")
    lease_token = payload.get("lease_token", "")
    result_data = payload.get("result", {})
    result = TaskResult.model_validate(result_data)
    if result.task_id != task_id:
        raise HTTPException(status_code=400, detail="Task ID mismatch between URL and payload")

    task_rec = await session.get(TaskRecord, task_id)
    if not task_rec:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(principal, task_rec.project_id)

    success = await TaskEngine.submit_result(session, result, lease_token, principal.subject)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to record task result")
    task_details = await session.get(TaskRecord, task_id)
    return {
        "status": "result_recorded",
        "task_status": task_details.status if task_details else result.status.value,
    }


@app.post("/api/tasks/{task_id}/approval")
async def decide_task_approval(
    task_id: str,
    payload: dict[str, Any],
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task_rec = res.scalar_one_or_none()
    if not task_rec:
        raise HTTPException(status_code=404, detail="Task not found")
    require_permission(principal, "spec:approve")
    require_project_access(principal, task_rec.project_id)

    approved = payload.get("approved")
    if not isinstance(approved, bool):
        raise HTTPException(status_code=422, detail="'approved' must be a boolean")
    reason = payload.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise HTTPException(status_code=422, detail="'reason' must be a string")
    packet_sha256 = payload.get("packet_sha256")
    review_sha256 = payload.get("review_sha256")
    try:
        task = await TaskEngine.decide_task_approval(
            session, task_id, approved, principal.subject, reason, packet_sha256, review_sha256
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not task:
        raise HTTPException(status_code=409, detail="Task is not awaiting a pending approval")
    return {"status": task.status, "task_id": task.id}


@app.get("/api/tasks/{task_id}")
async def get_task_details(
    task_id: str,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(_principal, task.project_id)
    if not (_principal.has_permission("task:read") or _principal.has_permission("project:read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{_principal.role.value}' lacks permission 'task:read'",
        )
    require_project_access(_principal, task.project_id)

    res_attempts = await session.execute(
        select(AttemptRecord)
        .where(AttemptRecord.task_id == task_id)
        .order_by(AttemptRecord.started_at.desc())
    )
    attempts = res_attempts.scalars().all()

    res_appr = await session.execute(
        select(ApprovalRecord)
        .where(
            and_(
                ApprovalRecord.task_id == task_id,
                ApprovalRecord.status == ApprovalStatus.PENDING.value,
            )
        )
        .order_by(ApprovalRecord.created_at.desc())
        .limit(1)
    )
    pending_appr = res_appr.scalar_one_or_none()

    response = {
        "task_id": task.id,
        "project_id": task.project_id,
        "objective": task.objective,
        "status": task.status,
        "risk_class": task.risk_class,
        "preferred_agent": task.preferred_agent,
        "attempts": [
            {
                "attempt_id": a.id,
                "agent": a.agent,
                "model": a.model,
                "status": a.status,
                "result_commit": a.result_commit,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in attempts
        ],
    }

    if pending_appr:
        response["pending_approval"] = {
            "approval_type": pending_appr.approval_type,
            "scope_sha256": pending_appr.scope_sha256,
        }

    return response


@app.get("/api/projects/{project_id}/progress")
async def get_project_progress(
    project_id: str,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "project:read")
    require_project_access(_principal, project_id)
    snapshot = await TaskEngine.project_progress_snapshot(session, project_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Project not found")
    return snapshot


# ==========================================
# Durable Project Event Log Endpoints
# ==========================================

EVENT_CATEGORY_MAP: dict[str, str] = {
    # project
    "project_created": "project",
    "project_updated": "project",
    "project_deleted": "project",
    "spec_submitted": "project",
    "spec_approved": "project",
    "spec_rejected": "project",
    "spec_extracted": "project",
    "decision_logged": "project",
    "open_question_logged": "project",
    "open_question_resolved": "project",
    "task_graph_generated": "project",
    "task_graph_draft_saved": "project",
    "task_graph_submitted": "project",
    "approval_decided": "project",
    # task
    "task_created": "task",
    "task_queued": "task",
    "task_leased": "task",
    "task_completed": "task",
    "task_failed": "task",
    "task_cancelled": "task",
    "task_canceled": "task",
    "task_retry": "task",
    "task_promoted": "task",
    "task_blocked": "task",
    "task_reset": "task",
    "task_attempt_started": "task",
    "task_attempt_completed": "task",
    # work
    "task_heartbeat": "work",
    "task_checkpoint": "work",
    "checkpoint_recorded": "work",
    "worktree_created": "work",
    "worker_registered": "work",
    "worker_heartbeat": "work",
    "worker_assigned": "work",
    # qa
    "gate_evidence_submitted": "qa",
    "qa_review_passed": "qa",
    "qa_review_failed": "qa",
    "lint_passed": "qa",
    "lint_failed": "qa",
    "test_passed": "qa",
    "test_failed": "qa",
    "gate_passed": "qa",
    "gate_failed": "qa",
    "review_submitted": "qa",
    # preview
    "preview_ready": "preview",
    "preview_deployed": "preview",
    "preview_stopped": "preview",
    "preview_url_generated": "preview",
    "deployment_started": "preview",
    "deployment_completed": "preview",
    # incident
    "watchdog_stalled": "incident",
    "worker_failed": "incident",
    "task_stalled": "incident",
    "circuit_breaker_tripped": "incident",
    "worker_crash": "incident",
    "security_violation": "incident",
    "lease_expired": "incident",
    "lease_revoked": "incident",
    "watchdog_alert": "incident",
}

VALID_EVENT_CATEGORIES = frozenset({"project", "task", "work", "qa", "preview", "incident"})


def classify_event_category(event_type: str) -> str:
    if event_type in EVENT_CATEGORY_MAP:
        return EVENT_CATEGORY_MAP[event_type]
    if (
        event_type.startswith("project_")
        or event_type.startswith("spec_")
        or event_type.startswith("decision_")
        or event_type.startswith("approval_")
    ):
        return "project"
    if (
        event_type.startswith("task_")
        and not event_type.startswith("task_heartbeat")
        and not event_type.startswith("task_checkpoint")
    ):
        return "task"
    if (
        event_type.startswith("gate_")
        or event_type.startswith("qa_")
        or event_type.startswith("test_")
        or event_type.startswith("lint_")
    ):
        return "qa"
    if event_type.startswith("preview_") or event_type.startswith("deployment_"):
        return "preview"
    if (
        event_type.startswith("watchdog_")
        or "incident" in event_type
        or "stall" in event_type
        or "breaker" in event_type
        or "crash" in event_type
        or "violation" in event_type
    ):
        return "incident"
    return "work"


def encode_event_cursor(timestamp: datetime, event_id: str) -> str:
    payload = {"timestamp": timestamp.isoformat(), "id": event_id}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decode_event_cursor(cursor_str: str) -> tuple[datetime, str]:
    try:
        raw_bytes = base64.b64decode(cursor_str.encode("ascii"), validate=True)
        payload = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON dictionary")
        if "id" not in payload or "timestamp" not in payload:
            raise ValueError("Missing 'id' or 'timestamp'")
        event_id = str(payload["id"])
        if not event_id:
            raise ValueError("Event id cannot be empty")
        ts_str = str(payload["timestamp"])
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt, event_id
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid pagination cursor: {exc}",
        ) from exc


def sanitize_client_event_details(details: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    if depth > 10:
        return {}
    cleaned = redact_dict(details)
    excluded_terms = (
        "secret",
        "token",
        "password",
        "key",
        "auth",
        "telemetry",
        "prompt",
        "path",
        "worktree",
        "repo",
        "storage",
        "lease",
        "worker",
        "cost",
        "sha256",
        "internal",
    )
    result: dict[str, Any] = {}
    for k, v in cleaned.items():
        k_lower = k.lower().replace("-", "_")
        if any(term in k_lower for term in excluded_terms):
            continue
        if isinstance(v, dict):
            sub = sanitize_client_event_details(v, depth + 1)
            if sub:
                result[k] = sub
        elif isinstance(v, str):
            if "/" in v and ("Users" in v or "repos" in v or "alphaBrain" in v):
                continue
            result[k] = redact_secrets(v)
        elif isinstance(v, list):
            sanitized_list: list[Any] = []
            for item in v:
                if isinstance(item, dict):
                    sub = sanitize_client_event_details(item, depth + 1)
                    if sub:
                        sanitized_list.append(sub)
                elif isinstance(item, str):
                    if not ("/" in item and ("Users" in item or "repos" in item)):
                        sanitized_list.append(redact_secrets(item))
                else:
                    sanitized_list.append(item)
            result[k] = sanitized_list
        else:
            result[k] = v
    return result


@app.get("/api/projects/{project_id}/events")
async def get_project_events(
    project_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    category: str | None = Query(default=None),
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    require_permission(_principal, "audit:read")
    require_project_access(_principal, project_id)

    # 1. Verify project exists
    project = await session.get(ProjectRecord, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    # 2. Validate category if provided
    if category is not None and category not in VALID_EVENT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event category: '{category}'. Valid categories are: {sorted(VALID_EVENT_CATEGORIES)}",
        )

    # 3. Build query
    query = select(AuditEventRecord).where(AuditEventRecord.project_id == project_id)

    if category:
        if category == "work":
            other_types = [k for k, v in EVENT_CATEGORY_MAP.items() if v != "work"]
            work_types = [k for k, v in EVENT_CATEGORY_MAP.items() if v == "work"]
            query = query.where(
                or_(
                    AuditEventRecord.event_type.in_(work_types),
                    ~AuditEventRecord.event_type.in_(other_types),
                )
            )
        else:
            cat_types = [k for k, v in EVENT_CATEGORY_MAP.items() if v == category]
            query = query.where(AuditEventRecord.event_type.in_(cat_types))

    if cursor:
        cursor_dt, cursor_id = decode_event_cursor(cursor)
        query = query.where(
            or_(
                AuditEventRecord.timestamp < cursor_dt,
                and_(
                    AuditEventRecord.timestamp == cursor_dt,
                    AuditEventRecord.id < cursor_id,
                ),
            )
        )

    query = query.order_by(AuditEventRecord.timestamp.desc(), AuditEventRecord.id.desc()).limit(
        limit + 1
    )

    result = await session.execute(query)
    records = result.scalars().all()

    has_more = len(records) > limit
    page_records = records[:limit]

    next_cursor = None
    if has_more and page_records:
        last_rec = page_records[-1]
        if last_rec.timestamp:
            next_cursor = encode_event_cursor(last_rec.timestamp, last_rec.id)

    # Format events according to viewer principal role
    formatted_events = []
    for rec in page_records:
        rec_cat = classify_event_category(rec.event_type)
        raw_details = rec.details_json if isinstance(rec.details_json, dict) else {}

        if _principal.role == PrincipalRole.CLIENT:
            actor = "system"
            actor_role = "system"
            details = sanitize_client_event_details(raw_details)
        else:
            actor = rec.actor
            actor_role = rec.actor_role
            details = redact_dict(raw_details)

        formatted_events.append(
            {
                "id": rec.id,
                "project_id": rec.project_id,
                "task_id": rec.task_id,
                "event_type": rec.event_type,
                "category": rec_cat,
                "actor": actor,
                "actor_role": actor_role,
                "details": details,
                "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
            }
        )

    return {
        "events": formatted_events,
        "returned_count": len(formatted_events),
        "next_cursor": next_cursor,
    }


# ==========================================
# Specification Intelligence Endpoints
# ==========================================


@app.post("/api/specs/extract")
async def extract_specification(
    payload: dict[str, str],
    _principal: AuthPrincipal = Depends(require_api_principal),
):
    transcript_text = payload.get("transcript", "")
    project_id = payload.get("project_id", "prj_default")
    title = payload.get("title", "Generated Specification")

    require_permission(_principal, "spec:write")
    require_project_access(_principal, project_id)

    if not transcript_text:
        raise HTTPException(status_code=400, detail="Transcript text is required")

    spec = SpecExtractor.parse_extraction_json(
        json.dumps(
            {
                "requirements": [
                    {
                        "req_id": "req_01",
                        "title": "Transcript Ingestion",
                        "raw_quote": transcript_text[:100],
                        "description": "Ingest and process user meeting notes",
                        "acceptance_criteria": ["Parsed accurately into spec schema"],
                        "priority": "must_have",
                    }
                ],
                "decisions": [
                    {
                        "dec_id": "dec_01",
                        "topic": "Architecture",
                        "decision": "Use Alpha Brain Zero-Cost Master Engine",
                        "rationale": "High throughput and no external API bill for code",
                    }
                ],
                "open_questions": [],
            }
        ),
        project_id=project_id,
        title=title,
    )
    return spec.model_dump()


# ==========================================
# Telephony & Plivo Webhook Endpoints
# ==========================================


@app.post("/api/voice/plivo/incoming")
async def plivo_incoming_call(request: Request):
    if not settings.PLIVO_AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="Plivo authentication is not configured")
    if not settings.ALPHA_SIGNING_SECRET:
        raise HTTPException(status_code=503, detail="Voice stream signing is not configured")

    body = await request.body()
    params = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    public_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{request.url.path}"
    if request.url.query:
        public_url += f"?{request.url.query}"
    signature = request.headers.get("X-Plivo-Signature-V3", "")
    nonce = request.headers.get("X-Plivo-Signature-V3-Nonce", "")
    signature_valid = validate_plivo_v3_signature(
        method=request.method,
        uri=public_url,
        nonce=nonce,
        auth_token=settings.PLIVO_AUTH_TOKEN,
        supplied_signatures=signature,
        params=params,
    )
    if not signature_valid or not plivo_nonce_cache.consume(nonce):
        raise HTTPException(status_code=401, detail="Invalid or replayed Plivo signature")

    stream_token = create_scoped_stream_token("plivo-media", ttl_seconds=300)
    parsed_base = urlsplit(settings.PUBLIC_BASE_URL)
    ws_scheme = "wss" if parsed_base.scheme == "https" else "ws"
    ws_url = urlunsplit(
        (
            ws_scheme,
            parsed_base.netloc,
            "/api/voice/plivo/media",
            f"stream_token={quote(stream_token)}",
            "",
        )
    )

    plivo_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream keepCallAlive="true" bidirectional="true" contentType="audio/x-l16;rate=8000">
        {xml_escape(ws_url)}
    </Stream>
</Response>
"""
    return Response(content=plivo_xml, media_type="application/xml")


@app.websocket("/api/voice/plivo/media")
async def plivo_media_websocket(websocket: WebSocket):
    if not verify_scoped_stream_token(
        websocket.query_params.get("stream_token"),
        "plivo-media",
    ):
        await websocket.close(code=4401)
        return
    await websocket.accept()

    job = CallJob(
        notification_id="ntf_live_call",
        persona=PersonaType.EVA,
        recipient_phone="+1234567890",
        purpose="live_telephony",
        idempotency_key="idemp_live",
    )
    bridge = PlivoVoiceBridge(job)

    try:
        while True:
            raw_text = await websocket.receive_text()
            bridge.handle_plivo_media_message(raw_text)
    except WebSocketDisconnect:
        logger.info("Plivo media WebSocket disconnected")
    except Exception as exc:
        logger.warning("Plivo media WebSocket failed: %s", redact_secrets(str(exc)))


import hashlib  # noqa: E402

from alpha_core.db.models import TaskCheckpointRecord  # noqa: E402
from alpha_protocol.task import (  # noqa: E402
    AppendCheckpointRequest,
    ResumeDecisionRequest,
    ResumeDecisionResponse,
    TaskCheckpoint,
)


@app.post("/api/tasks/{task_id}/checkpoints")
async def append_task_checkpoint(
    task_id: str,
    payload: AppendCheckpointRequest,
    _principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:write")

    if task_id != payload.checkpoint.task_id:
        raise HTTPException(status_code=400, detail="URL task_id does not match payload task_id")

    # 1. Fetch task and check lease
    res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(_principal, task.project_id)

    now = datetime.now(UTC)
    if task.status not in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}:
        raise HTTPException(status_code=409, detail="Task is not active or leased")

    if not task.lease_token or task.lease_token != payload.raw_lease_token:
        raise HTTPException(status_code=403, detail="Invalid lease token")

    from alpha_core.state.task_engine import normalize_utc

    if task.lease_expires_at and normalize_utc(task.lease_expires_at) < now:
        raise HTTPException(status_code=403, detail="Stale lease token")

    if task.worker_id and task.worker_id != payload.checkpoint.worker_id:
        raise HTTPException(status_code=403, detail="Worker mismatch")

    # Verify lease_token_hash matches
    expected_hash = hashlib.sha256(payload.raw_lease_token.encode("utf-8")).hexdigest()
    if payload.checkpoint.lease_token_hash != expected_hash:
        raise HTTPException(status_code=400, detail="lease_token_hash mismatch")

    # 2. Check for duplicate/out-of-order sequence
    res_chk = await session.execute(
        select(TaskCheckpointRecord)
        .where(
            TaskCheckpointRecord.task_id == task_id,
            TaskCheckpointRecord.attempt_number == payload.checkpoint.attempt_number,
        )
        .order_by(TaskCheckpointRecord.sequence.desc())
    )
    checkpoints = res_chk.scalars().all()

    for chk in checkpoints:
        if chk.idempotency_key == payload.checkpoint.idempotency_key:
            if chk.payload_digest == payload.checkpoint.payload_digest:
                # Same idempotency key + same digest returns existing checkpoint
                return payload.checkpoint.model_dump()
            else:
                # Same idempotency key + different digest rejects
                raise HTTPException(
                    status_code=409, detail="Idempotency key conflict with different digest"
                )

    highest_seq = checkpoints[0].sequence if checkpoints else 0
    if payload.checkpoint.sequence <= highest_seq:
        raise HTTPException(
            status_code=409,
            detail=f"Sequence {payload.checkpoint.sequence} must be > {highest_seq}",
        )

    if payload.checkpoint.sequence != highest_seq + 1:
        raise HTTPException(
            status_code=409, detail=f"Sequence {payload.checkpoint.sequence} out of order"
        )

    # 3. Create Checkpoint Record
    new_chk = TaskCheckpointRecord(
        id=payload.checkpoint.checkpoint_id,
        task_id=payload.checkpoint.task_id,
        attempt_id=payload.checkpoint.attempt_id,
        worker_id=payload.checkpoint.worker_id,
        attempt_number=payload.checkpoint.attempt_number,
        sequence=payload.checkpoint.sequence,
        project_id=payload.checkpoint.project_id,
        repo_reference=payload.checkpoint.repo_reference,
        base_commit=payload.checkpoint.base_commit,
        worktree_path=payload.checkpoint.worktree_path,
        worktree_head=payload.checkpoint.worktree_head,
        conversation_id=payload.checkpoint.conversation_id,
        execution_stage=payload.checkpoint.execution_stage,
        lease_token_hash=payload.checkpoint.lease_token_hash,
        side_effect_state=payload.checkpoint.side_effect_state.value,
        scrubbed_payload=payload.checkpoint.scrubbed_payload,
        payload_digest=payload.checkpoint.payload_digest,
        idempotency_key=payload.checkpoint.idempotency_key,
        created_at=payload.checkpoint.created_at,
    )
    session.add(new_chk)

    # Also log to engine as scrubbed payload progress if possible, but schema requires it
    # We will just commit it.
    await session.commit()

    return payload.checkpoint.model_dump()


@app.get("/api/tasks/{task_id}/checkpoints/latest")
async def get_latest_task_checkpoint(
    task_id: str,
    _principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:read")

    task = await session.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(_principal, task.project_id)

    res = await session.execute(
        select(TaskCheckpointRecord)
        .where(TaskCheckpointRecord.task_id == task_id)
        .order_by(TaskCheckpointRecord.attempt_number.desc(), TaskCheckpointRecord.sequence.desc())
        .limit(1)
    )
    chk = res.scalar_one_or_none()
    if not chk:
        raise HTTPException(status_code=404, detail="No checkpoints found for task")

    return TaskCheckpoint(
        checkpoint_id=chk.id,
        task_id=chk.task_id,
        attempt_id=chk.attempt_id,
        worker_id=chk.worker_id,
        attempt_number=chk.attempt_number,
        sequence=chk.sequence,
        project_id=chk.project_id,
        repo_reference=chk.repo_reference,
        base_commit=chk.base_commit,
        worktree_path=chk.worktree_path,
        worktree_head=chk.worktree_head,
        conversation_id=chk.conversation_id,
        execution_stage=chk.execution_stage,
        lease_token_hash=chk.lease_token_hash,
        side_effect_state=chk.side_effect_state,
        scrubbed_payload=chk.scrubbed_payload,
        payload_digest=chk.payload_digest,
        idempotency_key=chk.idempotency_key,
        created_at=chk.created_at,
    ).model_dump()


@app.post("/api/tasks/{task_id}/resume-decision")
async def get_resume_decision(
    task_id: str,
    payload: ResumeDecisionRequest,
    _principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:write")

    res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(_principal, task.project_id)

    # 1. Fetch latest checkpoint
    res_chk = await session.execute(
        select(TaskCheckpointRecord)
        .where(TaskCheckpointRecord.task_id == task_id)
        .order_by(TaskCheckpointRecord.attempt_number.desc(), TaskCheckpointRecord.sequence.desc())
        .limit(1)
    )
    latest_chk = res_chk.scalar_one_or_none()

    if not latest_chk:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="No prior checkpoint found"
        ).model_dump()

    if latest_chk.payload_digest != payload.latest_checkpoint_digest:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Checkpoint digest mismatch"
        ).model_dump()

    if latest_chk.project_id != payload.project_id:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Project ID mismatch"
        ).model_dump()

    if latest_chk.repo_reference != payload.repo_reference:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Repository mismatch"
        ).model_dump()

    if latest_chk.base_commit != payload.base_commit:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Base commit mismatch"
        ).model_dump()

    if latest_chk.worker_id != payload.worker_id:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Worker mismatch for local worktree"
        ).model_dump()

    if latest_chk.attempt_id != payload.attempt_id:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Attempt ID mismatch"
        ).model_dump()

    if latest_chk.conversation_id != payload.conversation_id:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Conversation ID mismatch"
        ).model_dump()

    if latest_chk.worktree_path != payload.worktree_path:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Worktree path mismatch"
        ).model_dump()

    if latest_chk.side_effect_state in {"unknown", "committed"}:
        return ResumeDecisionResponse(
            safe_to_resume=False, reason="Unsafe side-effect state requires review"
        ).model_dump()

    # Re-lease the task with a NEW lease token.
    # We must not reuse the old lease token.
    if task.status not in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}:
        # if it failed or something, we can't resume it unless it's running
        return ResumeDecisionResponse(
            safe_to_resume=False, reason=f"Task is in {task.status} status"
        ).model_dump()

    import secrets

    new_token = f"lse_{secrets.token_urlsafe(32)}"
    task.lease_token = new_token
    # Set a new lease token but preserve the worker
    task.worker_id = payload.worker_id
    now = datetime.now(UTC)
    task.lease_expires_at = now + __import__("datetime").timedelta(seconds=1800)

    await session.commit()

    return ResumeDecisionResponse(safe_to_resume=True, new_lease_token=new_token).model_dump()


# ==========================================
# Result Promotion Endpoints
# ==========================================


class PromotionDecisionRequest(BaseModel):
    promotion_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved: bool
    reason: str | None = None


@app.post("/api/projects/{project_id}/promotions/decision")
async def decide_promotion(
    project_id: str,
    payload: PromotionDecisionRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Promotion approval requires founder access")
    require_project_access(principal, project_id)

    # Find the task_promotion approval by digest
    res = await session.execute(
        select(ApprovalRecord).where(
            and_(
                ApprovalRecord.approval_type == "task_promotion",
                ApprovalRecord.scope_sha256 == payload.promotion_digest,
            )
        )
    )
    approval = res.scalar_one_or_none()
    if not approval:
        raise HTTPException(
            status_code=404, detail="Promotion approval not found or digest mismatch"
        )

    task = await session.get(TaskRecord, approval.task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found in project")

    # Reconstruct digest to be absolutely sure
    att_res = await session.execute(
        select(AttemptRecord).where(AttemptRecord.id == approval.attempt_id)
    )
    attempt = att_res.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    envelope = TaskEngine._parse_task_envelope(task.details_json)

    # Fetch the approved task_review to get its digest
    review_res = await session.execute(
        select(ApprovalRecord)
        .where(
            and_(
                ApprovalRecord.task_id == task.id,
                ApprovalRecord.attempt_id == attempt.id,
                ApprovalRecord.approval_type == "task_review",
                ApprovalRecord.status == ApprovalStatus.APPROVED.value,
            )
        )
        .order_by(ApprovalRecord.decided_at.desc())
        .limit(1)
    )
    review_approval = review_res.scalar_one_or_none()
    if not review_approval:
        raise HTTPException(status_code=409, detail="Missing approved task_review for this attempt")

    changed_files = (
        attempt.files_changed_json
        if isinstance(attempt.files_changed_json, list)
        else (json.loads(attempt.files_changed_json) if attempt.files_changed_json else [])
    )

    req = PromotionRequest(
        task_id=task.id,
        project_id=task.project_id,
        attempt_id=attempt.id,
        worker_id=attempt.worker_id or "",
        repo=envelope.repo,
        base_commit=envelope.base_commit,
        result_commit=attempt.result_commit or "",
        files_changed=changed_files,
        allowed_paths=envelope.allowed_paths,
        review_sha256=review_approval.scope_sha256,
    )
    recomputed = compute_promotion_digest(req)
    if recomputed != payload.promotion_digest:
        raise HTTPException(status_code=409, detail="Promotion digest mismatch")

    if approval.status != ApprovalStatus.PENDING.value:
        expected_status = (
            ApprovalStatus.APPROVED.value if payload.approved else ApprovalStatus.REJECTED.value
        )
        if approval.status != expected_status:
            raise HTTPException(status_code=409, detail="Conflicting replay decision rejects")
        return {"status": approval.status, "task_id": task.id}

    now = utc_now()
    approval.status = (
        ApprovalStatus.APPROVED.value if payload.approved else ApprovalStatus.REJECTED.value
    )
    approval.decided_by = principal.subject
    approval.decided_at = now
    approval.reason = payload.reason

    if not payload.approved:
        TaskEngine._transition(task, TaskStatus.BLOCKED)

    session.add(
        AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="task_promotion_approved" if payload.approved else "task_promotion_rejected",
            project_id=task.project_id,
            task_id=task.id,
            actor=principal.subject,
            details_json={"attempt_id": attempt.id, "reason": payload.reason},
            timestamp=now,
        )
    )
    await session.flush()
    return {"status": approval.status, "task_id": task.id}


@app.post("/api/workers/{worker_id}/promotions/next")
async def fetch_next_promotion(
    worker_id: str,
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if worker_id != principal.subject:
        raise HTTPException(status_code=403, detail="Worker ID mismatch")

    # Find an approved task_promotion for an attempt by this worker, where task is still VERIFIED
    res = await session.execute(
        select(ApprovalRecord)
        .join(TaskRecord, TaskRecord.id == ApprovalRecord.task_id)
        .join(AttemptRecord, AttemptRecord.id == ApprovalRecord.attempt_id)
        .where(
            and_(
                ApprovalRecord.approval_type == "task_promotion",
                ApprovalRecord.status == ApprovalStatus.APPROVED.value,
                TaskRecord.status == TaskStatus.VERIFIED.value,
                AttemptRecord.worker_id == worker_id,
            )
        )
        .order_by(ApprovalRecord.decided_at.asc())
        .limit(1)
    )
    approval = res.scalar_one_or_none()
    if not approval:
        return {"status": "no_promotions_available"}

    task = await session.get(TaskRecord, approval.task_id)
    attempt = await session.get(AttemptRecord, approval.attempt_id)
    if not task or not attempt:
        raise HTTPException(status_code=500, detail="Task or attempt record missing")
    require_project_access(principal, task.project_id)

    review_res = await session.execute(
        select(ApprovalRecord)
        .where(
            and_(
                ApprovalRecord.task_id == task.id,
                ApprovalRecord.attempt_id == attempt.id,
                ApprovalRecord.approval_type == "task_review",
                ApprovalRecord.status == ApprovalStatus.APPROVED.value,
            )
        )
        .order_by(ApprovalRecord.decided_at.desc())
        .limit(1)
    )
    review_approval = review_res.scalar_one_or_none()
    if not review_approval:
        raise HTTPException(status_code=500, detail="Approved task_review record missing")

    envelope = TaskEngine._parse_task_envelope(task.details_json)
    changed_files = (
        attempt.files_changed_json
        if isinstance(attempt.files_changed_json, list)
        else (json.loads(attempt.files_changed_json) if attempt.files_changed_json else [])
    )

    req = PromotionRequest(
        task_id=task.id,
        project_id=task.project_id,
        attempt_id=attempt.id,
        worker_id=worker_id,
        repo=envelope.repo,
        base_commit=envelope.base_commit,
        result_commit=attempt.result_commit or "",
        files_changed=changed_files,
        allowed_paths=envelope.allowed_paths,
        review_sha256=review_approval.scope_sha256,
    )

    recomputed = compute_promotion_digest(req)
    if recomputed != approval.scope_sha256:
        raise HTTPException(status_code=500, detail="Digest corruption in DB")

    return {"status": "promotion_available", "promotion": req.model_dump(mode="json")}


@app.post("/api/tasks/{task_id}/promotions/result")
async def submit_promotion_result(
    task_id: str,
    payload: dict[str, Any],
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    result_data = payload.get("result", {})
    try:
        result = PromotionResult.model_validate(result_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid result payload") from exc

    if result.task_id != task_id:
        raise HTTPException(status_code=422, detail="Task ID mismatch")
    if result.worker_id != principal.subject:
        raise HTTPException(status_code=403, detail="Worker ID mismatch")

    task = await session.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(principal, task.project_id)

    res_promo = await session.execute(
        select(ApprovalRecord).where(
            and_(
                ApprovalRecord.task_id == task_id,
                ApprovalRecord.approval_type == "task_promotion",
                ApprovalRecord.scope_sha256 == result.promotion_digest,
                ApprovalRecord.status == ApprovalStatus.APPROVED.value,
            )
        )
    )
    promo_appr = res_promo.scalar_one_or_none()
    if not promo_appr:
        raise HTTPException(
            status_code=404, detail="Approved promotion not found or digest mismatch"
        )

    att_res = await session.execute(
        select(AttemptRecord).where(AttemptRecord.id == promo_appr.attempt_id)
    )
    attempt = att_res.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.worker_id != principal.subject:
        raise HTTPException(status_code=403, detail="Not the producing worker")

    envelope = TaskEngine._parse_task_envelope(task.details_json)

    review_res = await session.execute(
        select(ApprovalRecord)
        .where(
            and_(
                ApprovalRecord.task_id == task.id,
                ApprovalRecord.attempt_id == attempt.id,
                ApprovalRecord.approval_type == "task_review",
                ApprovalRecord.status == ApprovalStatus.APPROVED.value,
            )
        )
        .order_by(ApprovalRecord.decided_at.desc())
        .limit(1)
    )
    review_approval = review_res.scalar_one_or_none()
    if not review_approval:
        raise HTTPException(status_code=409, detail="Missing approved task_review for this attempt")

    changed_files = (
        attempt.files_changed_json
        if isinstance(attempt.files_changed_json, list)
        else (json.loads(attempt.files_changed_json) if attempt.files_changed_json else [])
    )
    promo_req = PromotionRequest(
        task_id=task.id,
        project_id=task.project_id,
        attempt_id=attempt.id,
        worker_id=attempt.worker_id or "",
        repo=envelope.repo,
        base_commit=envelope.base_commit,
        result_commit=attempt.result_commit or "",
        files_changed=changed_files,
        allowed_paths=envelope.allowed_paths,
        review_sha256=review_approval.scope_sha256,
    )
    fresh_digest = compute_promotion_digest(promo_req)
    if fresh_digest != result.promotion_digest:
        raise HTTPException(
            status_code=409, detail="Promotion digest mismatch with recomputed state"
        )

    if task.status != TaskStatus.VERIFIED.value:
        if task.status == TaskStatus.COMPLETED.value and result.status == "succeeded":
            audit_res = await session.execute(
                select(AuditEventRecord).where(
                    and_(
                        AuditEventRecord.task_id == task_id,
                        AuditEventRecord.event_type == "task_promotion_succeeded",
                        AuditEventRecord.actor == principal.subject,
                    )
                )
            )
            for audit in audit_res.scalars():
                if (
                    isinstance(audit.details_json, dict)
                    and audit.details_json.get("promotion_digest") == result.promotion_digest
                ):
                    return {"status": "ok"}
        elif task.status == TaskStatus.BLOCKED.value and result.status == "failed":
            audit_res = await session.execute(
                select(AuditEventRecord).where(
                    and_(
                        AuditEventRecord.task_id == task_id,
                        AuditEventRecord.event_type == "task_promotion_failed",
                        AuditEventRecord.actor == principal.subject,
                    )
                )
            )
            for audit in audit_res.scalars():
                if (
                    isinstance(audit.details_json, dict)
                    and audit.details_json.get("promotion_digest") == result.promotion_digest
                ):
                    return {"status": "ok"}
        raise HTTPException(
            status_code=409, detail=f"Arbitrary replay rejected. Task status is {task.status}"
        )

    now = utc_now()
    if result.status == "succeeded":
        TaskEngine._transition(task, TaskStatus.COMPLETED)
        event_type = "task_promotion_succeeded"
    else:
        TaskEngine._transition(task, TaskStatus.BLOCKED)
        event_type = "task_promotion_failed"

    session.add(
        AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            project_id=task.project_id,
            task_id=task.id,
            actor=principal.subject,
            details_json={"promotion_digest": result.promotion_digest, "reason": result.reason},
            timestamp=now,
        )
    )

    # No auto-retry
    await session.flush()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Phase 9: Task Triage Queue & Human-in-the-Loop (HITL) Review Endpoints
# ---------------------------------------------------------------------------


class TriageApproveRequest(BaseModel):
    notes: str | None = None
    force: bool = False


class TriageRejectRequest(BaseModel):
    reason: str


class TriageModifyRequest(BaseModel):
    allowed_paths: list[str] | None = None
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    new_envelope: dict[str, Any] | None = None


class TriageEmergencyStopRequest(BaseModel):
    reason: str = "operator_requested_via_api"


_default_triage_queue: TaskTriageQueue | None = None


def get_triage_queue() -> TaskTriageQueue:
    global _default_triage_queue
    if _default_triage_queue is None:
        _default_triage_queue = TaskTriageQueue()
    return _default_triage_queue


def require_triage_access(principal: AuthPrincipal) -> None:
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Triage queue operations require founder or admin access",
        )


@app.get("/api/triage/stats")
async def get_triage_stats(
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    """Returns aggregate telemetry and operational metrics for the triage pipeline."""
    require_triage_access(principal)
    return queue.get_stats()


@app.get("/api/triage/tasks")
async def list_triage_tasks(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    parsed_status = None
    if status_filter and status_filter.lower() != "all":
        try:
            parsed_status = TriageStatus(status_filter.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{status_filter}'. Choices: {[s.value for s in TriageStatus]}",
            ) from None
    tasks = queue.list_tasks(status=parsed_status, limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/api/triage/tasks/{task_id}")
async def get_triage_task(
    task_id: str,
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found"
        )
    project_id = task.get("envelope", {}).get("project_id")
    if not project_id:
        logger.error(f"Task '{task_id}' missing project_id field in envelope", extra={"task_id": task_id})
        raise HTTPException(status_code=500, detail="Task missing project_id")
    require_project_access(principal, project_id)
    return dict(task)


@app.post("/api/triage/tasks/{task_id}/review")
async def review_triage_task(
    task_id: str,
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found"
        )
    project_id = task.get("envelope", {}).get("project_id")
    if not project_id:
        logger.error(f"Task '{task_id}' missing project_id field in envelope", extra={"task_id": task_id})
        raise HTTPException(status_code=500, detail="Task missing project_id")
    require_project_access(principal, project_id)
    safety_gate = SafetyGate()
    verdict = safety_gate.evaluate_envelope(task["envelope"])
    return {
        "task_id": task_id,
        "passed": verdict.passed,
        "status": verdict.verdict,
        "reason": verdict.reason,
        "violations": verdict.violations,
    }


@app.post("/api/triage/tasks/{task_id}/approve")
async def approve_triage_task(
    task_id: str,
    payload: TriageApproveRequest = TriageApproveRequest(),
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found"
        )
    project_id = task.get("envelope", {}).get("project_id")
    if not project_id:
        logger.error(f"Task '{task_id}' missing project_id field in envelope", extra={"task_id": task_id})
        raise HTTPException(status_code=500, detail="Task missing project_id")
    require_project_access(principal, project_id)

    if queue.is_emergency_stopped():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Emergency stop is active. Cannot approve tasks.",
        )

    # Validate SafetyGate verdict
    safety_gate = SafetyGate()
    verdict = safety_gate.evaluate_envelope(task["envelope"])
    if not verdict.passed and not payload.force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Safety Gate rejected task: {verdict.reason}. Pass force=true to override.",
        )

    notes = payload.notes or f"Approved by {principal.subject} via API"
    success = queue.approve_task(task_id, safety_verdict=verdict.verdict, safety_reason=notes)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve task '{task_id}'. Ensure current status is 'pending_review'.",
        )
    return {"status": "ok", "task_id": task_id, "state": "approved"}


@app.post("/api/triage/tasks/{task_id}/reject")
async def reject_triage_task(
    task_id: str,
    payload: TriageRejectRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found"
        )
    project_id = task.get("envelope", {}).get("project_id")
    if not project_id:
        logger.error(f"Task '{task_id}' missing project_id field in envelope", extra={"task_id": task_id})
        raise HTTPException(status_code=500, detail="Task missing project_id")
    require_project_access(principal, project_id)

    success = queue.reject_task(task_id, reason=payload.reason)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject task '{task_id}'. Current status: {task['status']}",
        )
    return {"status": "ok", "task_id": task_id, "state": "rejected"}


@app.post("/api/triage/tasks/{task_id}/modify")
async def modify_triage_task(
    task_id: str,
    payload: TriageModifyRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found"
        )
    project_id = task.get("envelope", {}).get("project_id")
    if not project_id:
        logger.error(f"Task '{task_id}' missing project_id field in envelope", extra={"task_id": task_id})
        raise HTTPException(status_code=500, detail="Task missing project_id")
    require_project_access(principal, project_id)

    try:
        success = queue.modify_task(
            task_id,
            new_envelope=payload.new_envelope,
            allowed_paths=payload.allowed_paths,
            title=payload.title,
            description=payload.description,
            reviewer_notes=payload.notes or f"Modified by {principal.subject} via API",
        )
    except EmergencyStopActiveError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot modify task '{task_id}'. Task must be in 'pending_review' status.",
        )

    # Re-evaluate safety gate immediately after modification
    updated_task = queue.get_task(task_id)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found after modification",
        )
    safety_gate = SafetyGate()
    verdict = safety_gate.evaluate_envelope(updated_task["envelope"])
    return {
        "status": "ok",
        "task_id": task_id,
        "safety_passed": verdict.passed,
        "safety_verdict": verdict.verdict,
        "safety_reason": verdict.reason,
        "safety_violations": verdict.violations,
    }


@app.get("/api/triage/emergency-status")
async def get_triage_emergency_status(
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    return dict(queue.get_emergency_status())


@app.post("/api/triage/emergency-stop")
async def post_triage_emergency_stop(
    payload: TriageEmergencyStopRequest = TriageEmergencyStopRequest(),
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    lock_path = queue.emergency_stop(reason=payload.reason)
    return {"emergency_stop": True, "lock_path": str(lock_path), "reason": payload.reason}


@app.post("/api/triage/emergency-resume")
async def post_triage_emergency_resume(
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_access(principal)
    resumed = queue.emergency_resume()
    return {"emergency_stop": False, "resumed": resumed}


class TriageWorkerLeaseRequest(BaseModel):
    worker_id: str | None = None


class TriageTaskResultRequest(BaseModel):
    status: str  # "completed" | "failed"
    result: dict[str, Any] = {}
    worktree_path: str | None = None
    branch_name: str | None = None
    error: str | None = None
    worker_id: str
    lease_id: str
    fencing_epoch: int
    attempt_id: str


def require_triage_worker_access(principal: AuthPrincipal) -> None:
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN, PrincipalRole.WORKER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Triage worker operations require founder, admin, or worker access",
        )


@app.post("/api/triage/tasks/lease")
async def post_triage_lease_task(
    payload: TriageWorkerLeaseRequest = TriageWorkerLeaseRequest(),
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_worker_access(principal)
    if queue.is_emergency_stopped():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Emergency stop active. Worker leasing suspended.",
        )
    task = queue.lease_next_approved_task(worker_id=principal.subject)
    if task:
        try:
            require_project_access(principal, task["envelope"]["project_id"])
        except HTTPException as e:
            # Compensating transaction: release lease without burning retries (Gemini Pro + Opus Invariant I-33)
            logger.warning(
                "Unauthorized tenant lease attempt for task %s by worker %s; releasing lease",
                task["id"],
                principal.subject,
            )
            released = queue.release_lease(
                task_id=task["id"],
                worker_id=task["worker_id"],
                lease_id=task["lease_id"],
                fencing_epoch=task["fencing_epoch"],
                attempt_id=task["attempt_id"],
                reason="tenant_access_denied",
            )
            if not released:
                logger.error(
                    "CAS failure releasing lease for task %s (task may have been reaped or reassigned)",
                    task["id"],
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized tenant access",
            ) from e
    return {"status": "ok", "task": task}


@app.post("/api/triage/tasks/{task_id}/result")
async def post_triage_task_result(
    task_id: str,
    payload: TriageTaskResultRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> dict[str, Any]:
    require_triage_worker_access(principal)
    if not SAFE_EXTERNAL_ID.fullmatch(task_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid task ID"
        )

    task_rec = queue.get_task(task_id)
    if not task_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task_rec.get("status") != "executing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task not executing")

    lease_meta = task_rec.get("provenance", {}).get("lease_metadata", {})
    if (
        lease_meta.get("worker_id") != payload.worker_id
        or lease_meta.get("lease_id") != payload.lease_id
        or lease_meta.get("fencing_epoch") != payload.fencing_epoch
        or lease_meta.get("attempt_id") != payload.attempt_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lease fencing violation: Ownership proof failed",
        )

    if payload.status == "completed":
        # A3 SLSA Provenance: Prevent executor from minting review/promotion evidence
        forbidden_fields = {"senior_review", "promotion_id", "promotion_approved"}
        if any(field in payload.result for field in forbidden_fields):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Executor cannot submit trusted senior_review or promotion fields in its own result.",
            )

        success = queue.complete_task(
            task_id,
            result=payload.result,
            worktree_path=payload.worktree_path,
            branch_name=payload.branch_name,
            worker_id=payload.worker_id,
            lease_id=payload.lease_id,
            fencing_epoch=payload.fencing_epoch,
            attempt_id=payload.attempt_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task '{task_id}' concurrent modification or fencing violated",
            )
        return {"status": "ok", "task_id": task_id, "state": "completed"}
    elif payload.status == "failed":
        success = queue.fail_task(
            task_id,
            error_details={"error": payload.error or "Unknown worker failure"},
            worker_id=payload.worker_id,
            lease_id=payload.lease_id,
            fencing_epoch=payload.fencing_epoch,
            attempt_id=payload.attempt_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task '{task_id}' concurrent modification or fencing violated",
            )
        return {"status": "ok", "task_id": task_id, "state": "failed"}
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{payload.status}'. Must be 'completed' or 'failed'",
        )


# ==========================================
# Portal API Endpoints
# ==========================================


@app.get("/api/portal/overview", response_model=dict[str, Any])
async def get_portal_overview(
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
):
    """Returns portal overview stats and metrics."""
    require_permission(principal, "audit:read")

    is_founder = principal.role in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}
    if is_founder:
        return {"status": "ok", "stats": queue.get_stats()}

    tasks = queue.list_tasks(limit=100000)
    authorized_tasks = [
        t
        for t in tasks
        if principal.can_access_project(t.get("envelope", {}).get("project_id", ""))
    ]

    import statistics

    status_counts = {s.value: 0 for s in TriageStatus}
    queue_waits = []
    exec_durations = []

    for t in authorized_tasks:
        status_val = t.get("status")
        if status_val in status_counts:
            status_counts[status_val] += 1

        telemetry = queue.get_task_telemetry(t["id"])
        qw = telemetry.get("queue_wait_seconds")
        if qw is not None:
            queue_waits.append(qw)
        ed = telemetry.get("execution_duration_seconds")
        if ed is not None:
            exec_durations.append(ed)

    stats = {
        "total_tasks": len(authorized_tasks),
        "by_status": status_counts,
        "queue_wait_seconds": {
            "average": float(statistics.mean(queue_waits)) if queue_waits else 0.0,
            "median": float(statistics.median(queue_waits)) if queue_waits else 0.0,
        },
        "execution_duration_seconds": {
            "average": float(statistics.mean(exec_durations)) if exec_durations else 0.0,
            "median": float(statistics.median(exec_durations)) if exec_durations else 0.0,
        },
    }
    return {"status": "ok", "stats": stats}


@app.get("/api/portal/tasks/{task_id}/trace", response_model=dict[str, Any])
async def get_portal_task_trace(
    task_id: str,
    principal: AuthPrincipal = Depends(require_api_principal),
    queue: TaskTriageQueue = Depends(get_triage_queue),
):
    """Returns provenance, attestation, and telemetry for a specific task."""
    require_permission(principal, "task:read")

    if not SAFE_EXTERNAL_ID.fullmatch(task_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid task ID"
        )

    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Enforce tenant isolation (Invariant I-33)
    project_id = task.get("envelope", {}).get("project_id")
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Task missing project ownership",
        )
    require_project_access(principal, project_id)

    # Redact attestation to prevent raw data exposure
    senior_review = task.get("result", {}).get("senior_review", {}) if task.get("result") else None
    redacted_attestation = redact_dict(senior_review) if senior_review else None

    provenance = task.get("provenance", {})
    is_founder = principal.role in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}
    if not is_founder:
        allowed_keys = {
            "meeting_id",
            "speaker_id",
            "utterance_timestamp",
            "transcript_excerpt",
            "extraction_model",
            "extraction_confidence",
            "eva_session_id",
            "created_at",
            "content_hash",
        }
        provenance = {k: v for k, v in provenance.items() if k in allowed_keys}

    return {
        "status": "ok",
        "task_id": task_id,
        "task_state": (
            "completed"
            if (task.get("result") or {}).get("promotion", {}).get("result_sha")
            else "review"
            if task.get("status") == "completed"
            else task.get("status", "pending_review")
        ),
        "provenance": provenance,
        "attestation": redacted_attestation,
        "telemetry": queue.get_task_telemetry(task_id),
    }


async def portal_stream_generator(
    project_id: str,
    last_event_id: str | None = None,
    max_duration_seconds: int = 3600,
    poll_interval_seconds: float = 1.0,
    max_iterations: int | None = None,
    queue: TaskTriageQueue | None = None,
):
    """SSE generator streaming genuine task events with durable monotonic replay and heartbeat."""
    if queue is None:
        queue = get_triage_queue()

    deadline = asyncio.get_event_loop().time() + max_duration_seconds
    current_seq = int(last_event_id) if last_event_id and str(last_event_id).isdigit() else 0
    iterations = 0
    last_heartbeat_time = 0.0

    try:
        while asyncio.get_event_loop().time() < deadline:
            iterations += 1
            events = await asyncio.to_thread(queue.get_project_events, project_id, current_seq, 50)
            if events:
                for ev in events:
                    current_seq = ev["seq"]
                    try:
                        sanitized = sanitize_client_event_details(ev.get("payload", {}))
                        commentary = await asyncio.to_thread(
                            live_commentary_engine.translate_event, ev["event_type"], sanitized
                        )
                    except Exception as e:
                        logger.error("Commentary engine error: %s", redact_secrets(str(e)))
                        commentary = f"Event: {ev['event_type']}"

                    data = {
                        "project_id": ev["project_id"],
                        "task_id": ev["task_id"],
                        "state": ev["state"],
                        "status": ev["status"],
                        "event_type": ev["event_type"],
                        "created_at": ev["created_at"],
                        "live": True,
                        "commentary": commentary,
                    }
                    yield f"id: {current_seq}\nevent: task_update\ndata: {json.dumps(data)}\n\n"
            else:
                now = asyncio.get_event_loop().time()
                if (now - last_heartbeat_time) >= 15.0 or last_heartbeat_time == 0.0:
                    last_heartbeat_time = now
                    yield f"id: {current_seq}\nevent: heartbeat\ndata: {{}}\n\n"

            if max_iterations is not None and iterations >= max_iterations:
                break

            await asyncio.sleep(poll_interval_seconds)
    except asyncio.CancelledError:
        pass


@app.post("/api/portal/projects/{project_id}/stream/token")
async def get_portal_stream_token(
    project_id: str,
    principal: AuthPrincipal = Depends(require_api_principal),
):
    require_permission(principal, "audit:read")
    require_project_access(principal, project_id)
    return {"token": create_scoped_stream_token(f"portal-stream:{project_id}", ttl_seconds=3600)}


@app.get("/api/portal/projects/{project_id}/stream", response_class=StreamingResponse)
async def stream_portal_events(
    project_id: str,
    request: Request,
    token: str = Query(...),
    max_iterations: int | None = Query(default=None),
    queue: TaskTriageQueue = Depends(get_triage_queue),
):
    if not verify_scoped_stream_token(token, f"portal-stream:{project_id}"):
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")
    last_event_id = request.headers.get("Last-Event-ID") or request.query_params.get(
        "last_event_id"
    )
    return StreamingResponse(
        portal_stream_generator(
            project_id, last_event_id, max_iterations=max_iterations, queue=queue
        ),
        media_type="text/event-stream",
    )
