from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionStage(str, Enum):
    """Execution stages for task-to-model routing."""

    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    QA = "qa"
    MECHANICAL = "mechanical"


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
    allowed_models: list[str] = Field(default_factory=list)
    claude_budget_allowed: bool = False
    required_capabilities: list[str] = Field(default_factory=list)
    tool_needs: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    """Deterministic output from the model router."""

    status: RoutingDecisionStatus
    model: str | None = None
    effort: str | None = None
    account_id: str | None = None
    rationale_codes: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    independence_status: str | None = None
    founder_review_required: bool = False
    earliest_retry_at: datetime | None = None
    retry_timestamp_known: bool = False
