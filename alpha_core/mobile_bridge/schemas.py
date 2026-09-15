"""
alpha_core/mobile_bridge/schemas.py
Pydantic schemas for AlphaBrain Founder Companion mobile bridge (P14).
Supports all 14 DeployMate Locomotive screens and real-time telemetry.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TriageAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskSummary(BaseModel):
    task_id: str
    title: str
    category: str = "engineering"
    status: str
    priority: TaskPriority = TaskPriority.NORMAL
    risk_class: str = "low"
    created_at: float
    updated_at: float
    author: str = "Eva CTO"
    allowed_paths: list[str] = Field(default_factory=list)
    acceptance_commands: list[str] = Field(default_factory=list)


class TaskDetail(TaskSummary):
    description: str = ""
    branch_name: str | None = None
    worktree_path: str | None = None
    review_notes: str | None = None
    gate_results: dict[str, Any] = Field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    action: TriageAction
    founder_notes: str = ""
    override_reason: str | None = None


class ReviewResponse(BaseModel):
    task_id: str
    previous_status: str
    new_status: str
    success: bool
    message: str


class DiffFile(BaseModel):
    file_path: str
    status: str  # added, modified, deleted
    additions: int
    deletions: int
    patch: str


class TaskDiffResponse(BaseModel):
    task_id: str
    base_commit: str
    head_commit: str
    files: list[DiffFile]
    total_additions: int
    total_deletions: int


class PromotionResponse(BaseModel):
    task_id: str
    merge_status: str
    fast_forward: bool
    commit_sha: str
    merged_at: float


class VoiceBriefing(BaseModel):
    briefing_id: str
    timestamp: float
    speaker: str = "Eva (DeployMate CTO)"
    audio_active: bool = False
    executive_summary: str
    recommended_actions: list[str]
    active_room: str = "deploymate-main"


class SpokenCommandRequest(BaseModel):
    command_text: str
    target_project: str = "alphabrain_dogfood"
    context_notes: str = ""


class SpokenCommandResponse(BaseModel):
    acknowledged: bool
    interpreted_action: str
    proposed_task_id: str | None = None
    eva_response_text: str


class WorkerSlot(BaseModel):
    worker_id: str
    status: str  # idle, running, cooling
    current_task_id: str | None = None
    worktree_slug: str | None = None
    uptime_seconds: float = 0.0
    turn_count: int = 0


class SprintFleetOverview(BaseModel):
    fleet_name: str = "AlphaBrain Autonomous Swarm"
    max_workers: int
    active_workers: int
    slots: list[WorkerSlot]
    queue_backlog: int
    adaptive_throttle_factor: float = 1.0


class DeploymentTarget(BaseModel):
    id: str
    service_name: str
    provider: str  # Vercel, Render, Supabase
    environment: str  # production, staging, preview
    status: str  # healthy, deploying, degraded, failed
    live_url: str
    last_deployed_at: float
    commit_sha: str
    rollback_available: bool = True


class RollbackRequest(BaseModel):
    target_commit_sha: str | None = None
    reason: str = "Founder companion instant rollback"


class CircuitBreakerStatus(BaseModel):
    name: str
    state: str  # closed, open, half_open
    failure_count: int
    threshold: int
    last_failure_at: float | None = None


class SelfHealingRadar(BaseModel):
    daemon_running: bool = True
    active_healers: int = 1
    recent_repairs_count: int = 0
    circuit_breakers: list[CircuitBreakerStatus]
    last_incident: str | None = None


class HardwareTelemetry(BaseModel):
    host_cpu_percent: float
    host_ram_percent: float
    host_ram_used_gb: float
    host_ram_total_gb: float
    thermal_pressure: str = "nominal"  # nominal, fair, serious, critical
    battery_level_percent: float = 100.0
    battery_charging: bool = True
    usb_device_connected: bool = True
    usb_device_serial: str = "10BF5P2AZF0010T"
    usb_device_name: str = "iQOO 12 Flagship"


class PrivacyConsentStats(BaseModel):
    total_records: int
    retention_days_limit: int = 90
    redaction_enabled: bool = True
    gdpr_status: str = "compliant"
    pending_purges: int = 0
    last_purge_at: float | None = None


class ModelUtilityScore(BaseModel):
    account_name: str
    email: str
    tier: str  # Tier 1, Tier 2, Tier 3, Tier 4
    utility_score: float
    weekly_quota_percent: float
    five_hour_quota_percent: float
    recommended_model: str = "claude-opus-4-6-thinking"
    gemini_5h_percent: float = 100.0
    gemini_weekly_percent: float = 100.0
    gemini_5h_desc: str = ""
    gemini_weekly_desc: str = ""
    claude_5h_percent: float = 100.0
    claude_weekly_percent: float = 100.0
    claude_5h_desc: str = ""
    claude_weekly_desc: str = ""
    token_status: str = "valid"
    is_active: bool = False


class AuditLogEntry(BaseModel):
    event_id: str
    timestamp: float
    actor: str
    action_type: str
    resource_id: str
    sha256_hash: str
    details: dict[str, Any] = Field(default_factory=dict)


class EmergencyStopState(BaseModel):
    active: bool
    locked_at: float | None = None
    lock_file: str
    reason: str = ""
    triggered_by: str = ""


class EmergencyStopToggleRequest(BaseModel):
    enable_stop: bool
    reason: str = "Manual toggle from Founder Companion app"


class ExecutiveOverview(BaseModel):
    app_version: str = "1.0.0-locomotive"
    system_status: str = "operational"
    emergency_stop: EmergencyStopState
    telemetry: HardwareTelemetry
    triage_backlog_count: int
    active_sprint_workers: int
    recent_deployments_count: int
    eva_status: str = "active"


class DashboardScreenData(BaseModel):
    system_status: str = "operational"
    emergency_stop: EmergencyStopState
    telemetry: HardwareTelemetry
    ai_quotas_summary: str = "100% AVAILABLE"
    ai_quotas_percent: float = 100.0
    active_projects_count: int = 0
    tech_dept_agents_count: int = 0
    triage_pending_count: int = 0
    worktrees_count: int = 0
    worktrees_summary: str = "Active"
    hardware_sync_serial: str = "10BF5P2AZF0010T"


class CommandNodeMetrics(BaseModel):
    cpu_usage: float
    memory_used_mb: float
    memory_total_mb: float
    disk_used_gb: float
    disk_total_gb: float
    uptime_seconds: float
    active_workers: int


class CommandNodeTask(BaseModel):
    id: str
    title: str
    priority: str = "P0"
    branch: str = ""
    status: str = "running"
    duration: str = "--"


class CommandNodeLog(BaseModel):
    id: str
    timestamp: str
    stream: str = "system"
    text: str


class CommandNodeScreenData(BaseModel):
    node_id: str
    hostname: str
    cluster_name: str
    status: str
    metrics: CommandNodeMetrics
    active_tasks: list[CommandNodeTask]
    logs: list[CommandNodeLog]


class ApiVaultItem(BaseModel):
    id: str
    name: str
    key_alias: str
    masked_value: str
    last_used: str = "Active"
    in_keychain: bool = True
    is_configured: bool = True


class TrustedDevice(BaseModel):
    id: str
    name: str
    platform: str
    sas_code: str
    paired_at: str
    status: str = "active"


class SecurityEnclaveScreenData(BaseModel):
    node_key_fingerprint: str
    is_locked: bool = False
    vault_items: list[ApiVaultItem]
    devices: list[TrustedDevice]
    emergency_stop_active: bool = False


class MeetingSetupScreenData(BaseModel):
    room_name: str
    livekit_url: str
    token: str
    participant_identity: str
    audio_codec: str = "opus"
    sample_rate: int = 48000
    audio_active: bool = True
    video_active: bool = False
    status: str = "ready"


class MeetingTokenResponse(BaseModel):
    token: str
    room_name: str
    expires_in_seconds: int = 3600


# =====================================================================
# Amazon-Style Delivery Board & Milestone Progress
# =====================================================================

class DeliveryMilestone(BaseModel):
    id: str
    step_number: int
    title: str
    status: str  # "completed", "in_transit", "pending"
    summary: str
    timestamp_label: str
    actor: str
    checkpoint_badge: str


class DeliveryMapResponse(BaseModel):
    project_id: str
    project_name: str
    overall_progress_percent: int
    active_step: int
    total_steps: int
    stages: list[DeliveryMilestone]
    inflight_task: dict[str, Any]
    metrics: dict[str, Any]


# =====================================================================
# Executive Architecture Reading Room
# =====================================================================

class ExecutiveDocSummary(BaseModel):
    doc_id: str
    title: str
    category: str  # "architecture", "senior_plan", "tech_stack", "meeting_spec"
    file_path: str
    summary: str
    word_count: int
    last_modified: float
    author: str


class ExecutiveDocDetail(BaseModel):
    doc_id: str
    title: str
    category: str
    file_path: str
    content_markdown: str
    sections: list[str]
    last_modified: float
    author: str


# =====================================================================
# Client & Delegate Access Control (Admin Delegation)
# =====================================================================

class DelegateCredential(BaseModel):
    delegate_id: str
    member_name: str
    role: str  # "client_viewer", "team_delegate", "delegated_admin"
    passcode: str
    created_at: float
    is_active: bool = True
    can_admin_verdict: bool = False


class DelegateInviteRequest(BaseModel):
    member_name: str
    role: str = "client_viewer"
    notes: str = ""
    grant_admin_access: bool = False


class DelegateAuthRequest(BaseModel):
    delegate_id: str
    passcode: str


class DelegateAuthResponse(BaseModel):
    authenticated: bool
    token: str
    member_name: str
    role: str
    can_admin_verdict: bool
    message: str


# =====================================================================
# Feedback, Problem Tickets & Admin Triage Handover
# =====================================================================

class FeedbackItem(BaseModel):
    id: str
    project_id: str
    author_name: str
    author_role: str
    problem_title: str
    problem_description: str
    created_at: float
    status: str  # "pending_admin", "handed_over", "rejected", "resolved"
    eva_analysis: str | None = None
    eva_proposed_task: dict[str, Any] | None = None
    admin_notes: str | None = None
    admitted_task_id: str | None = None


class FeedbackCreateRequest(BaseModel):
    author_name: str
    author_role: str = "client"
    problem_title: str
    problem_description: str


class AdminFeedbackVerdictRequest(BaseModel):
    action: str  # "handover_pipeline", "dismiss_rejected", "resolve_direct"
    admin_notes: str = ""
    reviewer_name: str = "Founder"

