from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .enums import AgentType, RiskClass, TaskStatus
from .gates import AcceptancePlan, GateResult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskDependency(BaseModel):
    task_id: str
    required_status: TaskStatus = TaskStatus.COMPLETED


class TaskEnvelope(BaseModel):
    """Task dispatched to worker plane."""
    task_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="Unique task identifier, e.g. tsk_101",
    )
    project_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="Parent project ID, e.g. prj_alpha",
    )
    repo: str = Field(min_length=1, max_length=512, description="Repository path or identifier")
    base_commit: str = Field(
        default="HEAD",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/@{}~^+-]{0,127}$",
        description="Git base commit/branch",
    )
    objective: str = Field(description="Clear, actionable task objective")
    detailed_instructions: Optional[str] = Field(default=None, description="Detailed markdown instructions")
    inputs: List[str] = Field(default_factory=list, description="Input artifact references")
    allowed_paths: List[str] = Field(
        min_length=1,
        description="Scoped relative paths allowed to be touched; use '.' explicitly for whole repo",
    )
    allowed_tools: List[str] = Field(default_factory=list, description="Allowed tool or MCP names")
    risk_class: RiskClass = RiskClass.LOW
    acceptance_plan: AcceptancePlan = Field(default_factory=AcceptancePlan)
    preferred_agent: AgentType = AgentType.ANTIGRAVITY
    session_id: Optional[str] = Field(default=None, description="Dedicated Antigravity or memory_graph session ID")
    lease_timeout_seconds: int = Field(default=1800, description="Task lease timeout (default 30 mins)")
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("allowed_paths")
    @classmethod
    def validate_allowed_paths(cls, paths: List[str]) -> List[str]:
        for raw_path in paths:
            if raw_path == ".":
                continue
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("allowed_paths must contain safe relative paths")
        return paths


class TaskAttempt(BaseModel):
    """Represents a single execution attempt by an agent adapter."""
    attempt_id: str = Field(description="Unique attempt ID, e.g. att_101_1")
    task_id: str
    agent: AgentType
    model: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.RUNNING
    worktree_path: Optional[str] = None


class TaskResult(BaseModel):
    """Structured result returned by an agent adapter upon completing an attempt."""
    attempt_id: str
    task_id: str
    status: TaskStatus
    agent: AgentType
    model: str
    base_commit: str
    result_commit: Optional[str] = None
    files_changed: List[str] = Field(default_factory=list)
    diff_summary: Optional[str] = None
    gate_result: Optional[GateResult] = None
    artifacts: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    provenance_notes: List[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=utc_now)
