from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProvenanceRecord(BaseModel):
    agent: str
    model: str
    prompt_hash: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None


class AuditEvent(BaseModel):
    event_id: str
    event_type: str = Field(description="e.g. task_leased, gate_passed, approval_granted, call_placed")
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    actor: str = Field(description="system, founder, client, or worker")
    details: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[ProvenanceRecord] = None
    timestamp: datetime = Field(default_factory=utc_now)
