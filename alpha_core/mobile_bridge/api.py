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

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from alpha_core.mobile_bridge.schemas import (
    AuditLogEntry,
    DeploymentTarget,
    EmergencyStopState,
    EmergencyStopToggleRequest,
    ExecutiveOverview,
    HardwareTelemetry,
    ModelUtilityScore,
    PrivacyConsentStats,
    PromotionResponse,
    ReviewRequest,
    ReviewResponse,
    RollbackRequest,
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
    return app
