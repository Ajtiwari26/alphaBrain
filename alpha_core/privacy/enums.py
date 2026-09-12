from enum import Enum


class ConsentType(str, Enum):
    VOICE_RECORDING = "voice_recording"
    TELEPHONIC_OUTREACH = "telephonic_outreach"
    AI_PROCESSING = "ai_processing"
    DATA_RETENTION = "data_retention"
    MARKETING_COMMUNICATION = "marketing_communication"


class DataClass(str, Enum):
    TRANSCRIPTS = "transcripts"
    MEETING_EVENTS = "meeting_events"
    CALL_RECORDS = "call_records"
    WORKER_HEALTH = "worker_health"
    TASK_CHECKPOINTS = "task_checkpoints"
    REVOKED_CONSENTS = "revoked_consents"
    AUDIT_EVENTS = "audit_events"
