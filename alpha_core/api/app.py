import asyncio
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit
from xml.sax.saxutils import escape as xml_escape

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from alpha_core.security import (
    AuthPrincipal,
    PrincipalRole,
    create_meeting_invite,
    create_scoped_stream_token,
    create_worker_identity_token,
    plivo_nonce_cache,
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
eva_meet_agent = EvaMeetingAgent()
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

    leased_tuple = await TaskEngine.lease_next_task(
        session,
        worker_id,
        preferred_agent=preferred_agent,
        lease_duration_seconds=settings.WORKER_LEASE_DURATION_SECONDS,
    )
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
    success = await TaskEngine.record_heartbeat(session, task_id, lease_token, principal.subject)
    if not success:
        task = await session.get(TaskRecord, task_id)
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
from datetime import UTC, datetime  # noqa: E402

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
