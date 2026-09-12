from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from alpha_core.privacy.enums import ConsentType


class ConsentRecordRequest(BaseModel):
    user_id: str | None = None
    phone_number: str | None = None
    project_id: str | None = None
    org_id: str | None = None
    consent_type: ConsentType | str
    granted: bool = True
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsentWithdrawalRequest(BaseModel):
    user_id: str | None = None
    phone_number: str | None = None
    project_id: str | None = None
    consent_type: ConsentType | str | None = None
    reason: str | None = None


class ConsentResponse(BaseModel):
    id: str
    user_id: str | None
    phone_number: str | None
    project_id: str | None
    org_id: str | None
    consent_type: str
    granted: bool
    ip_address: str | None
    user_agent: str | None
    recorded_at: datetime
    revoked_at: datetime | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsentListResponse(BaseModel):
    consents: list[ConsentResponse]
    total: int


class DataExportRequest(BaseModel):
    user_id: str | None = None
    phone_number: str | None = None
    email: str | None = None


class DataExportResponse(BaseModel):
    export_id: str
    subject_id: str
    exported_at: datetime
    user_profile: dict[str, Any] | None = None
    consents: list[dict[str, Any]] = Field(default_factory=list)
    call_jobs: list[dict[str, Any]] = Field(default_factory=list)
    meeting_participations: list[dict[str, Any]] = Field(default_factory=list)
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list)
    audit_summary: list[dict[str, Any]] = Field(default_factory=list)


class DataDeletionRequest(BaseModel):
    user_id: str | None = None
    phone_number: str | None = None
    email: str | None = None
    reason: str = "Right to be forgotten request"


class DataDeletionResponse(BaseModel):
    deletion_id: str
    subject_id: str
    status: str
    deleted_at: datetime
    records_affected: dict[str, int] = Field(default_factory=dict)
    audit_event_id: str


class RetentionPolicyConfig(BaseModel):
    ttls_days: dict[str, int] = Field(default_factory=dict)


class RetentionPruneRequest(BaseModel):
    custom_ttls_days: dict[str, int] | None = None
    dry_run: bool = False


class RetentionPruneResponse(BaseModel):
    pruned_counts: dict[str, int]
    total_pruned: int
    executed_at: datetime
    dry_run: bool
    cutoffs: dict[str, str] = Field(default_factory=dict)


class TelephonyValidationRequest(BaseModel):
    recipient_phone: str
    project_id: str | None = None
    require_recording_consent: bool = True
    disclosure_acknowledged: bool = True


class TelephonyValidationResponse(BaseModel):
    allowed: bool
    recipient_phone: str
    consent_id: str | None = None
    disclosure_verified: bool
    rejection_reason: str | None = None
