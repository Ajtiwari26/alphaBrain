from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from .enums import PersonaType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CallStatus(str, Enum):
    QUEUED = "queued"
    ACCEPTED = "accepted"
    DIALING = "dialing"
    ANSWERED = "answered"
    SPEAKING = "speaking"
    ACTION_PENDING = "action_pending"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    DECLINED = "declined"


class CallTranscriptItem(BaseModel):
    speaker: str = Field(description="ai or human")
    text: str
    timestamp: datetime = Field(default_factory=utc_now)


class CallTranscript(BaseModel):
    call_id: str
    items: List[CallTranscriptItem] = Field(default_factory=list)
    extracted_summary: Optional[str] = None
    action_items: List[str] = Field(default_factory=list)


class CallJob(BaseModel):
    """Job submitted to AgentLine to initiate an autonomous voice call."""
    notification_id: str
    persona: PersonaType = PersonaType.KAVYA
    recipient_phone: str
    recipient_name: Optional[str] = None
    project_id: Optional[str] = None
    purpose: str = Field(description="e.g. founder_preview_review, client_milestone_update")
    script_facts: Dict[str, Any] = Field(default_factory=dict, description="Verified facts model is allowed to state")
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of passing gates or preview URLs")
    idempotency_key: str
    status: CallStatus = CallStatus.QUEUED
    call_id: Optional[str] = None
    duration_seconds: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
