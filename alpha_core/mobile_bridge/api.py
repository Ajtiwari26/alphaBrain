"""
alpha_core/mobile_bridge/api.py
FastAPI router and application endpoints for AlphaBrain Founder Companion mobile app.
Serves all 14 DeployMate Locomotive screens with real-time SSE streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import pydantic
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from alpha_core.mobile_bridge.schemas import (
    # Amazon-style delivery, reading room, delegates, feedback schemas
    AdminFeedbackVerdictRequest,
    AuditLogEntry,
    CommandNodeScreenData,
    DashboardScreenData,
    DelegateAuthRequest,
    DelegateAuthResponse,
    DelegateCredential,
    DelegateInviteRequest,
    DeliveryMapResponse,
    DeploymentTarget,
    EmergencyStopState,
    EmergencyStopToggleRequest,
    ExecutiveDocDetail,
    ExecutiveDocSummary,
    ExecutiveOverview,
    FeedbackCreateRequest,
    FeedbackItem,
    HardwareTelemetry,
    MeetingSetupScreenData,
    MeetingTokenResponse,
    ModelUtilityScore,
    PrivacyConsentStats,
    PromotionResponse,
    ReviewRequest,
    ReviewResponse,
    RollbackRequest,
    SecurityEnclaveScreenData,
    SelfHealingRadar,
    SpokenCommandRequest,
    SpokenCommandResponse,
    SprintFleetOverview,
    TaskDetail,
    TaskDiffResponse,
    TaskSummary,
    VoiceBriefing,
)
from alpha_core.mobile_bridge.service import MobileBridgeService
from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal

logger = logging.getLogger("alphabrain.mobile_bridge.api")

router = APIRouter(prefix="/api/v1/mobile", tags=["Founder Companion Mobile Bridge"])
_default_service = MobileBridgeService()


def get_service() -> MobileBridgeService:
    return _default_service


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """Health check endpoint for mobile bridge connectivity."""
    return {
        "status": "healthy",
        "service": "alpha_mobile_bridge",
        "companion_version": "1.0.0-locomotive",
        "supported_screens": 14,
        "target_device": "10BF5P2AZF0010T",
    }


@router.get("/overview", response_model=ExecutiveOverview)
async def get_overview() -> ExecutiveOverview:
    """Screen 01: Executive Mission Control overview."""
    return get_service().get_executive_overview()


@router.get("/triage", response_model=list[TaskSummary])
async def list_triage(
    filter_status: str | None = Query(
        default=None, alias="status", description="Filter by status (pending_review, approved, etc.)"
    ),
) -> list[TaskSummary]:
    """Screen 02: Triage Queue tasks list."""
    return get_service().list_triage_tasks(status_filter=filter_status)


@router.post("/triage/{task_id}/review", response_model=ReviewResponse)
async def review_triage_task(task_id: str, request: ReviewRequest) -> ReviewResponse:
    """Screen 02: Submit founder review decision (approve / reject)."""
    return get_service().review_triage_task(
        task_id=task_id,
        action=request.action,
        founder_notes=request.founder_notes,
        override_reason=request.override_reason,
    )


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task_detail(task_id: str) -> TaskDetail:
    """Screen 03: Task Detail, spec reviewer, and execution checkpoint inspect."""
    detail = get_service().get_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")
    return detail


@router.get("/tasks/{task_id}/diff", response_model=TaskDiffResponse)
async def get_task_diff(task_id: str) -> TaskDiffResponse:
    """Screen 04: Interactive Git diff viewer."""
    return get_service().get_task_diff(task_id)


@router.post("/tasks/{task_id}/promote", response_model=PromotionResponse)
async def promote_task(task_id: str) -> PromotionResponse:
    """Screen 07: One-tap 'Approve & Merge' PR promotion handoff."""
    return get_service().promote_task(task_id)


@router.get("/voice/briefing", response_model=VoiceBriefing)
async def get_voice_briefing() -> VoiceBriefing:
    """Screen 05: Eva Voice executive AI briefing."""
    return get_service().get_voice_briefing()


@router.post("/voice/command", response_model=SpokenCommandResponse)
async def post_voice_command(request: SpokenCommandRequest) -> SpokenCommandResponse:
    """Screen 05: Spoken intake voice commanding."""
    result = get_service().interpret_spoken_command(request.command_text)
    return SpokenCommandResponse(**result)


@router.get("/sprint", response_model=SprintFleetOverview)
async def get_sprint_overview() -> SprintFleetOverview:
    """Screen 06: Autonomous worker swarm and sprint orchestration."""
    return get_service().get_sprint_overview()


@router.get("/deployments", response_model=list[DeploymentTarget])
async def list_deployments() -> list[DeploymentTarget]:
    """Screen 08: Multi-cloud deployments tracker (Vercel, Render, Supabase)."""
    return get_service().get_deployments()


@router.post("/deployments/{deployment_id}/rollback", response_model=dict[str, Any])
async def trigger_rollback(
    deployment_id: str, payload: RollbackRequest | None = None
) -> dict[str, Any]:
    """Screen 08: Instant deployment rollback."""
    reason = payload.reason if payload else "Manual founder rollback via mobile companion"
    return get_service().trigger_rollback(deployment_id, reason=reason)


@router.get("/self-healing", response_model=SelfHealingRadar)
async def get_self_healing() -> SelfHealingRadar:
    """Screen 09: CI/CD self-healing daemon and circuit breakers."""
    return get_service().get_self_healing_radar()


@router.get("/telemetry", response_model=HardwareTelemetry)
async def get_telemetry() -> HardwareTelemetry:
    """Screen 10: Real-time hardware telemetry and device status."""
    return get_service().get_hardware_telemetry()


@router.get("/privacy", response_model=PrivacyConsentStats)
async def get_privacy_stats() -> PrivacyConsentStats:
    """Screen 11: P13.1 Privacy, consent, and retention compliance."""
    return get_service().get_privacy_stats()


@router.post("/privacy/purge", response_model=dict[str, Any])
async def purge_privacy() -> dict[str, Any]:
    """Screen 11: Trigger GDPR / DPDP compliance purge."""
    return get_service().purge_privacy_data()


@router.get("/models", response_model=list[ModelUtilityScore])
async def get_model_scores() -> list[ModelUtilityScore]:
    """Screen 12: Multi-account OC-EDS model router utility scores."""
    return get_service().get_model_utility_scores()


@router.get("/worktrees", response_model=list[dict[str, Any]])
async def list_worktrees() -> list[dict[str, Any]]:
    """Screen 09: Git Worktrees status and active branches."""
    return get_service().get_git_worktrees()


@router.get("/projects", response_model=list[dict[str, Any]])
async def list_projects() -> list[dict[str, Any]]:
    """Screen 13: Real workspace projects from Desktop/Projects."""
    return get_service().get_projects()


@router.get("/audit", response_model=list[AuditLogEntry])
async def get_audit_trail(limit: int = Query(default=20, ge=1, le=100)) -> list[AuditLogEntry]:
    """Screen 13: Immutable cryptographic audit trail."""
    return get_service().get_audit_trail(limit=limit)


@router.get("/emergency-stop", response_model=EmergencyStopState)
async def get_emergency_stop() -> EmergencyStopState:
    """Screen 14: Founder emergency kill-switch status."""
    return get_service().get_emergency_stop_state()


@router.post("/emergency-stop", response_model=EmergencyStopState)
async def toggle_emergency_stop(request: EmergencyStopToggleRequest) -> EmergencyStopState:
    """Screen 14: Toggle founder emergency stop tombstone."""
    return get_service().set_emergency_stop(enable=request.enable_stop, reason=request.reason)


@router.get("/stream")
async def sse_event_stream(request: Request) -> StreamingResponse:
    """Real-time SSE event stream for mobile push updates."""

    async def event_generator():
        service = get_service()
        while True:
            if await request.is_disconnected():
                break
            telemetry = service.get_hardware_telemetry()
            emergency = service.get_emergency_stop_state()
            data = {
                "event": "tick",
                "timestamp": time.time(),
                "telemetry": telemetry.model_dump(),
                "emergency_stop": emergency.active,
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/dashboard", response_model=DashboardScreenData)
async def get_dashboard(
    principal: AuthPrincipal = Depends(require_api_principal),
) -> DashboardScreenData:
    """Dashboard Screen: Real production mission kernel and system metrics."""
    return get_service().get_dashboard_data()


@router.get("/command-node", response_model=CommandNodeScreenData)
async def get_command_node(
    node_id: str | None = Query(default=None, description="Optional node ID filter"),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> CommandNodeScreenData:
    """Command Node Screen: Real production execution node telemetry, tasks, and system logs."""
    return get_service().get_command_node_data(node_id=node_id)


@router.get("/security-enclave", response_model=SecurityEnclaveScreenData)
async def get_security_enclave(
    principal: AuthPrincipal = Depends(require_api_principal),
) -> SecurityEnclaveScreenData:
    """Security Enclave Screen: Real production API key vault, trusted devices, and node fingerprint."""
    return get_service().get_security_enclave_data()


@router.get("/meet/setup", response_model=MeetingSetupScreenData)
async def get_meeting_setup(
    room: str = Query(default="alphabrain-executive-briefing", description="Meeting room identifier"),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> MeetingSetupScreenData:
    """Meeting Setup Screen: Real LiveKit WebRTC room setup and authentication parameters."""
    role = "founder" if principal.role in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN} else "client"
    return get_service().get_meeting_setup_data(room_name=room, participant=principal.subject, role=role)


@router.get("/meet/token", response_model=MeetingTokenResponse)
async def get_meeting_token(
    room: str = Query(default="alphabrain-executive-briefing", description="Meeting room identifier"),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> MeetingTokenResponse:
    """Meeting Token Endpoint: Direct LiveKit SFU access token generation for companion and desktop."""
    role = "founder" if principal.role in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN} else "client"
    return get_service().get_meeting_token(room_name=room, participant=principal.subject, role=role)


class ConcludeMeetingRequest(pydantic.BaseModel):
    meeting_id: str
    transcripts: list[dict[str, Any]] = []


@router.post("/meet/{room}/conclude")
async def conclude_meeting(room: str, payload: ConcludeMeetingRequest | None = None) -> dict[str, Any]:
    """Conclude meeting and persist executive summary."""
    return {"status": "concluded", "room": room, "transcript_count": len(payload.transcripts) if payload else 0}


# =====================================================================
# Amazon-Style Delivery Board Endpoints
# =====================================================================

@router.get("/delivery-map", response_model=DeliveryMapResponse)
async def get_delivery_map(
    project_id: str = Query(default="alphabrain_dogfood", description="Project identifier"),
) -> DeliveryMapResponse:
    """Amazon-style project completion and delivery board with 7 sequential milestones."""
    return get_service().get_delivery_map(project_id=project_id)


# =====================================================================
# Executive Architecture Reading Room Endpoints
# =====================================================================

@router.get("/docs/index", response_model=list[ExecutiveDocSummary])
async def list_executive_docs() -> list[ExecutiveDocSummary]:
    """Catalog of all key architectural, roadmap, and meeting specifications."""
    return get_service().list_executive_docs()


@router.get("/docs/{doc_id}", response_model=ExecutiveDocDetail)
async def get_executive_doc(doc_id: str) -> ExecutiveDocDetail:
    """Detailed markdown content and section headers for a specific architectural doc."""
    try:
        return get_service().get_executive_doc(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document file for '{doc_id}' not found on disk.") from None


# =====================================================================
# Client & Delegate Access Control Endpoints
# =====================================================================

@router.get("/delegates/list", response_model=list[DelegateCredential])
async def list_delegates(
    principal: AuthPrincipal = Depends(require_api_principal),
) -> list[DelegateCredential]:
    """List all registered client viewers and team delegates."""
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or Founder role required to list delegates.",
        )
    return get_service().list_delegates(mask_passcode=True)


@router.post("/delegates/invite", response_model=DelegateCredential)
async def create_delegate_invite(
    req: DelegateInviteRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
) -> DelegateCredential:
    """Generate a shareable Client/Delegate ID & Passcode, optionally delegating admin access."""
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or Founder role required to create delegate invites.",
        )
    return get_service().create_delegate_invite(req)


@router.post("/delegates/auth", response_model=DelegateAuthResponse)
async def authenticate_delegate(req: DelegateAuthRequest) -> DelegateAuthResponse:
    """Authenticate with Delegate ID & Passcode."""
    return get_service().authenticate_delegate(req)


# =====================================================================
# Client Problem Tickets, Opinions & Admin Handover Endpoints
# =====================================================================

@router.get("/feedback", response_model=list[FeedbackItem])
async def list_feedback(
    project_id: str = Query(default="alphabrain_dogfood", description="Project identifier"),
) -> list[FeedbackItem]:
    """List all queries, tickets, and verdicts raised by clients or delegates."""
    return get_service().list_feedback(project_id=project_id)


@router.post("/feedback", response_model=FeedbackItem)
async def submit_feedback(
    req: FeedbackCreateRequest,
    project_id: str = Query(default="alphabrain_dogfood", description="Project identifier"),
) -> FeedbackItem:
    """Raise a problem ticket, opinion, or verdict request. Eva performs immediate diagnostic analysis."""
    return get_service().submit_feedback(req, project_id=project_id)


@router.post("/feedback/{feedback_id}/admin-verdict", response_model=FeedbackItem)
async def admin_verdict_on_feedback(
    feedback_id: str,
    verdict: AdminFeedbackVerdictRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
) -> FeedbackItem:
    """
    STRICT ADMIN PERMISSION INVARIANT:
    Founder or authorized Delegated Admin decides whether to:
    1. 'handover_pipeline': Enqueues a real remediation task into TaskTriageQueue!
    2. 'dismiss_rejected': Dismisses the issue as out-of-scope or duplicate.
    3. 'resolve_direct': Directly marks resolved with clarification notes.
    """
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invariant I-1 strictly restricts verdict execution to Founder and Admin roles.",
        )
    try:
        return get_service().admin_verdict_on_feedback(feedback_id, verdict, principal=principal)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from None
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feedback item '{feedback_id}' not found.") from None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@router.get("/voice/incoming")
async def get_incoming_call() -> dict[str, Any]:
    call = get_service().get_active_incoming_call()
    return {"active_call": call}

class RespondRequest(pydantic.BaseModel):
    action: str

@router.post("/voice/incoming/{call_id}/respond")
async def respond_incoming_call(call_id: str, request: RespondRequest) -> dict[str, Any]:
    return {"status": "ok", "call": get_service().respond_incoming_call(call_id, request.action)}

class TriggerCallRequest(pydantic.BaseModel):
    caller_name: str
    caller_role: str
    title: str
    prompt_summary: str
    task_id: str | None = None

@router.post("/voice/call/trigger")
async def trigger_inapp_call(request: TriggerCallRequest) -> dict[str, Any]:
    call = get_service().trigger_inapp_call(
        request.caller_name, request.caller_role, request.title, request.prompt_summary, request.task_id
    )
    return {"status": "dispatched", "call": call}

def create_mobile_bridge_app() -> FastAPI:
    """Factory to create a standalone FastAPI application for the mobile bridge."""
    app = FastAPI(
        title="AlphaBrain Founder Companion Mobile Bridge",
        version="1.0.0",
        description="High-throughput bridge powering all 14 DeployMate Locomotive screens",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.post("/api/meet/{room}/conclude")
    async def legacy_conclude_meeting(room: str, payload: ConcludeMeetingRequest | None = None) -> dict[str, Any]:
        return {"status": "concluded", "room": room, "transcript_count": len(payload.transcripts) if payload else 0}

    return app
