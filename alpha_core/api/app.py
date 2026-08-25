import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
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
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.config import settings
from alpha_core.db.connection import get_db_session, init_db
from alpha_core.db.models import AttemptRecord, TaskRecord
from alpha_core.security import (
    AuthPrincipal,
    create_meeting_invite,
    create_scoped_stream_token,
    plivo_nonce_cache,
    require_api_principal,
    require_worker_principal,
    validate_plivo_v3_signature,
    verify_meeting_invite,
    verify_scoped_stream_token,
    verify_websocket_bearer,
)
from alpha_core.state.task_engine import TaskEngine
from alpha_meet.eva_agent import EvaMeetingAgent
from alpha_meet.eva_live_agent import eva_room_manager
from alpha_meet.live_audio import LiveMeetAudioBridge
from alpha_meet.tokens import LiveKitTokenGenerator, MeetingRole
from alpha_protocol import (
    CallJob,
    PersonaType,
    TaskEnvelope,
    TaskResult,
)
from alpha_voice.extractor import SpecExtractor
from alpha_voice.plivo_bridge import PlivoVoiceBridge
from alpha_worker.worktree import WorktreeManager

MEET_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "alpha_meet" / "frontend"
eva_meet_agent = EvaMeetingAgent()
logger = logging.getLogger("alpha_core.api")
SAFE_EXTERNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await init_db()
    try:
        yield
    finally:
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
        eva_status = await eva_room_manager.ensure_room(room_name)
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
    slide = eva_meet_agent.generate_presentation_slide(project_name=project)
    return JSONResponse(slide)


@app.post("/api/meet/speak")
async def meet_speak(
    payload: dict[str, str],
    _principal: AuthPrincipal = Depends(require_api_principal),
):
    """Processes spoken input and generates Eva's CTO voice reply."""
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
    await bridge.run()


# ==========================================
# Task Management Endpoints
# ==========================================


@app.post("/api/tasks", response_model=dict[str, Any])
async def submit_task(
    envelope: TaskEnvelope,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        WorktreeManager.validate_repo_path(envelope.repo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    task = await TaskEngine.submit_task(session, envelope)
    return {"status": "queued", "task_id": task.id, "project_id": task.project_id}


@app.post("/api/tasks/lease")
async def lease_task(
    payload: dict[str, str],
    principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    worker_id = payload.get("worker_id", principal.subject)
    if not SAFE_EXTERNAL_ID.fullmatch(worker_id):
        raise HTTPException(status_code=422, detail="Invalid worker ID")
    preferred_agent = payload.get("preferred_agent")

    leased_tuple = await TaskEngine.lease_next_task(session, worker_id, preferred_agent)
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
    _principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    lease_token = payload.get("lease_token", "")
    success = await TaskEngine.record_heartbeat(session, task_id, lease_token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid lease token or task not found")
    return {"status": "heartbeat_recorded"}


@app.post("/api/tasks/{task_id}/result")
async def submit_task_result(
    task_id: str,
    payload: dict[str, Any],
    _principal: AuthPrincipal = Depends(require_worker_principal),
    session: AsyncSession = Depends(get_db_session),
):
    lease_token = payload.get("lease_token", "")
    result_data = payload.get("result", {})
    result = TaskResult.model_validate(result_data)
    if result.task_id != task_id:
        raise HTTPException(status_code=422, detail="Task ID does not match result body")

    success = await TaskEngine.submit_result(session, result, lease_token)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to record task result")
    return {"status": "result_recorded", "task_status": result.status.value}


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

    res_attempts = await session.execute(
        select(AttemptRecord)
        .where(AttemptRecord.task_id == task_id)
        .order_by(AttemptRecord.started_at.desc())
    )
    attempts = res_attempts.scalars().all()

    return {
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
        pass
    except Exception as exc:
        logger.warning("Plivo media WebSocket failed: %s", exc)
