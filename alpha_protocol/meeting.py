"""
Alpha Protocol Meeting Event Schemas v1
=========================================
Structured event types extracted from meeting conversations,
linking raw transcript quotes to classified requirements,
decisions, recommendations, and action items.

Protocol version: 1
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .enums import PROTOCOL_VERSION, MeetingEventType


def utc_now() -> datetime:
    return datetime.now(UTC)


class TranscriptSegment(BaseModel):
    """Raw timestamped transcript segment from a meeting."""

    segment_id: str
    room_name: str
    speaker_identity: str
    speaker_name: str
    text: str
    is_eva: bool = False
    timestamp: datetime = Field(default_factory=utc_now)
    duration_seconds: float | None = None


class MeetingEvent(BaseModel):
    """Structured event extracted from meeting transcript analysis."""

    protocol_version: Literal["1"] = Field(default=PROTOCOL_VERSION)
    event_id: str
    room_name: str
    project_id: str
    event_type: MeetingEventType
    title: str = Field(description="Short summary of the event")
    description: str = Field(description="Detailed description")
    raw_quote: str | None = Field(
        default=None,
        description="Direct transcript quote that sourced this event",
    )
    source_segment_ids: list[str] = Field(
        default_factory=list,
        description="IDs of transcript segments this event was derived from",
    )
    speaker_identity: str | None = None
    is_inference: bool = Field(
        default=False,
        description="True if this was inferred by AI rather than directly stated",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="AI confidence in extraction accuracy",
    )
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class MeetingSession(BaseModel):
    """Aggregated meeting session metadata."""

    session_id: str
    room_name: str
    project_id: str
    participants: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    segment_count: int = Field(default=0, ge=0)
    event_count: int = Field(default=0, ge=0)
    consent_recorded: bool = Field(
        default=False,
        description="Whether all participants consented to recording/transcription",
    )
