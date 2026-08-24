"""
Alpha Protocol Enums v1
=======================
Canonical status, type, and classification enumerations shared across
Unifold, Alpha Brain, AgentLine, Inito, and the Mac Worker.

Protocol version: 1
"""

from enum import Enum

PROTOCOL_VERSION = "1"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    VERIFIED = "verified"
    RETRYABLE_FAILED = "retryable_failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"


# Legal state transitions: (from_status) -> {allowed target statuses}
LEGAL_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.QUEUED: frozenset({TaskStatus.LEASED, TaskStatus.CANCELLED}),
    TaskStatus.LEASED: frozenset({
        TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.CANCELLED,
    }),
    TaskStatus.RUNNING: frozenset({
        TaskStatus.VERIFIED, TaskStatus.RETRYABLE_FAILED, TaskStatus.BLOCKED,
        TaskStatus.WAITING_APPROVAL, TaskStatus.CANCELLED, TaskStatus.QUEUED,
    }),
    TaskStatus.WAITING_APPROVAL: frozenset({
        TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.QUEUED,
    }),
    TaskStatus.VERIFIED: frozenset({TaskStatus.COMPLETED, TaskStatus.SUPERSEDED}),
    TaskStatus.RETRYABLE_FAILED: frozenset({TaskStatus.QUEUED, TaskStatus.CANCELLED}),
    TaskStatus.BLOCKED: frozenset({TaskStatus.QUEUED, TaskStatus.CANCELLED}),
    TaskStatus.CANCELLED: frozenset(),       # Terminal
    TaskStatus.SUPERSEDED: frozenset(),      # Terminal
    TaskStatus.COMPLETED: frozenset(),       # Terminal
}


def is_legal_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    """Check if a state transition is allowed by the protocol."""
    allowed = LEGAL_TRANSITIONS.get(from_status, frozenset())
    return to_status in allowed


class AgentType(str, Enum):
    ANTIGRAVITY = "antigravity"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    GEMINI = "gemini"
    STITCH = "stitch"


class AgentReadiness(str, Enum):
    """Agent availability states reported by adapters."""
    READY = "ready"
    BUSY = "busy"
    RATE_LIMITED = "rate_limited"
    AUTH_REQUIRED = "auth_required"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class RiskClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GateType(str, Enum):
    LINT = "lint"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    BUILD = "build"
    BROWSER_SMOKE = "browser_smoke"
    SECURITY_SCAN = "security_scan"
    INDEPENDENT_REVIEW = "independent_review"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class WorkerHealth(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    DRAINING = "draining"
    ASLEEP = "asleep"
    OFFLINE = "offline"


class PersonaType(str, Enum):
    EVA = "eva"        # Engineering persona (Unifold meet, SDLC review, technical updates)
    KAVYA = "kavya"    # Customer support / Intake persona (AgentLine default)


class MeetingEventType(str, Enum):
    """Structured event types extracted from meeting conversations."""
    RAW_REQUEST = "raw_request"
    CLARIFIED_REQUIREMENT = "clarified_requirement"
    EVA_RECOMMENDATION = "eva_recommendation"
    TRADE_OFF = "trade_off"
    DECISION = "decision"
    OPEN_QUESTION = "open_question"
    ACCEPTANCE_CRITERION = "acceptance_criterion"
    OWNER_ACTION = "owner_action"


class DeploymentStatus(str, Enum):
    """Deployment lifecycle statuses."""
    REQUESTED = "requested"
    BUILDING = "building"
    PREVIEW_READY = "preview_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class WorkflowPhase(str, Enum):
    """SDLC workflow lifecycle phases for Temporal orchestration."""
    INTAKE = "intake"
    DISCOVERY = "discovery"
    SPEC_DRAFT = "spec_draft"
    FOUNDER_REVIEW = "founder_review"
    CLIENT_REVIEW = "client_review"
    APPROVED = "approved"
    DESIGN = "design"
    BUILD = "build"
    VERIFY = "verify"
    PREVIEW = "preview"
    FOUNDER_ACCEPTANCE = "founder_acceptance"
    CLIENT_ACCEPTANCE = "client_acceptance"
    RELEASE_CANDIDATE = "release_candidate"
    PRODUCTION_APPROVAL = "production_approval"
    DEPLOYED = "deployed"
    MONITORING = "monitoring"
