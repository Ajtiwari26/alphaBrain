from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .enums import ApprovalStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


class Requirement(BaseModel):
    req_id: str
    title: str
    raw_quote: str | None = Field(default=None, description="Direct quote from meeting transcript or client message")
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: str = Field(default="medium", description="must_have, should_have, nice_to_have")
    tags: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    dec_id: str
    topic: str
    decision: str
    rationale: str
    alternatives_considered: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)


class OpenQuestion(BaseModel):
    question_id: str
    question: str
    context: str
    owner: str = "founder"  # founder or client
    resolved: bool = False
    answer: str | None = None


class SpecVersion(BaseModel):
    version: int = Field(default=1, description="Sequential spec version number")
    project_id: str
    title: str
    summary: str
    requirements: list[Requirement] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    architecture_overview: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    founder_approved: bool = False
    client_approved: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None


class SpecDocument(BaseModel):
    project_id: str
    active_version: int = 1
    versions: list[SpecVersion] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)
