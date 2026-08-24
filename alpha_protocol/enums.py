from enum import Enum


class TaskStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    VERIFIED = "verified"
    RETRYABLE_FAILED = "retryable_failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AgentType(str, Enum):
    ANTIGRAVITY = "antigravity"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    GEMINI = "gemini"


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
