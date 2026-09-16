from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

DEGRADED_SAME_FAMILY = "DEGRADED_SAME_FAMILY"
INDEPENDENT_CROSS_PROVIDER = "INDEPENDENT_CROSS_PROVIDER"


class IndependenceStatus(str, Enum):
    INDEPENDENT_CROSS_PROVIDER = "INDEPENDENT_CROSS_PROVIDER"
    DEGRADED_SAME_FAMILY = "DEGRADED_SAME_FAMILY"


class ModelTier(str, Enum):
    """Tri-tier model routing topology."""

    TIER_1_FAST = "tier_1_fast"
    TIER_2_STANDARD = "tier_2_standard"
    TIER_3_REASONING = "tier_3_reasoning"


class ConfidenceScore(BaseModel):
    """Structured confidence score for research broker queries and complexity gating."""

    score: float = Field(ge=0.0, le=1.0)
    source: str = "heuristic"
    strike_count: int = 0
    signals: list[str] = Field(default_factory=list)


class ComplexityGateConfig(BaseModel):
    """Configuration schema for ComplexityGate."""

    tier_1_model: str = "gemini-3.8-flash-high"
    tier_2_model: str = "gemini-3.1-pro-high"
    tier_3_model_claude: str = "claude-opus-4-6-thinking"
    tier_3_model_fallback: str = "claude-sonnet-4-6"
    tier_3_model_pro: str = "gemini-3.1-pro-high"
    confidence_escalation_threshold: float = 0.5
    confidence_acceleration_threshold: float = 0.8
    max_strikes_before_escalation: int = 3
    sensitive_path_patterns: list[str] = Field(
        default_factory=lambda: [
            "auth",
            "crypto",
            "security",
            "keys",
            "credential",
            "token",
            "signing",
            "protocol/routing",
            "billing",
            "payment",
        ]
    )


class DegradedSameFamilyAttestation(BaseModel):
    """Attestation stamped when cross-provider independence degrades to same family."""

    degraded_same_family: bool = True
    independence_status: str = DEGRADED_SAME_FAMILY
    round1_model: str
    round2_model: str
    fallback_reason: str
    founder_review_required: bool = True
    attested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionStage(str, Enum):
    """Execution stages for task-to-model routing."""

    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    QA = "qa"
    MECHANICAL = "mechanical"
    RESEARCH = "research"


class RoutingDecisionStatus(str, Enum):
    """Result of a routing decision."""

    SELECTED = "selected"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"


class AccountState(str, Enum):
    """Observed state of an account/model pair."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    COOLDOWN = "cooldown"
    AUTH_FAILED = "auth_failed"
    DISABLED = "disabled"


class AccountModelState(BaseModel):
    """Metadata tracking quota and availability for an account and model pair."""

    state: AccountState = AccountState.UNKNOWN
    last_selected_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_rate_limit_at: datetime | None = None
    next_eligible_at: datetime | None = None
    next_eligible_source: str | None = Field(
        None, description="e.g. provider, configured_fallback, manual"
    )
    last_failure_class: str | None = None
    rolling_successes: int = 0
    rolling_failures: int = 0


class RoutingRequest(BaseModel):
    """Input parameters for the deterministic model router."""

    project_id: str
    task_id: str
    attempt_id: str
    stage: ExecutionStage
    risk_class: str
    complexity_class: str
    implementation_model: str | None = None
    allowed_models: list[str] | None = None
    claude_budget_allowed: bool = False
    required_capabilities: list[str] = Field(default_factory=list)
    tool_needs: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    """Deterministic output from the model router."""

    model_config = ConfigDict(populate_by_name=True)

    status: RoutingDecisionStatus = Field(alias="decision")
    model: str | None = None
    effort: str | None = None
    account_id: str | None = Field(default=None, alias="account")
    rationale_codes: list[str] = Field(default_factory=list, alias="rationale")
    fallback_chain: list[str] = Field(default_factory=list)
    independence_status: str | None = Field(default=None, alias="independence")
    founder_review_required: bool = False
    earliest_retry_at: datetime | None = None
    retry_timestamp_known: bool = False
    confidence_score: float | None = None
    tier: str | None = None
    degraded_same_family: bool = False
    degraded_attestation: DegradedSameFamilyAttestation | None = None
