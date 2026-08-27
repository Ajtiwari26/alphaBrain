"""
Alpha Brain Notification Policy
===============================
Enforces strict routing: routine updates remain in the client/founder portal;
AgentLine voice calls trigger exclusively for urgent verified events:
- Urgent approval needed for high-risk blockers
- Repeated repair failures (stalled/blocked at max attempts)
- Milestone deadline risks
- Active worker loss during active task execution
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from alpha_protocol.enums import RiskClass


class NotificationTriggerType(str, Enum):
    URGENT_APPROVAL_NEEDED = "urgent_approval_needed"
    REPEATED_REPAIR_FAILURE = "repeated_repair_failure"
    DEADLINE_RISK = "deadline_risk"
    ACTIVE_WORKER_LOSS = "active_worker_loss"
    ROUTINE_SPEC_DRAFT = "routine_spec_draft"
    ROUTINE_TASK_COMPLETED = "routine_task_completed"
    ROUTINE_PREVIEW_READY = "routine_preview_ready"
    ROUTINE_DAILY_DIGEST = "routine_daily_digest"


class NotificationChannel(str, Enum):
    PORTAL = "portal"
    AGENTLINE_CALL = "agentline_call"


URGENT_CALL_TRIGGERS = frozenset(
    {
        NotificationTriggerType.URGENT_APPROVAL_NEEDED,
        NotificationTriggerType.REPEATED_REPAIR_FAILURE,
        NotificationTriggerType.DEADLINE_RISK,
        NotificationTriggerType.ACTIVE_WORKER_LOSS,
    }
)


class NotificationEvent(BaseModel):
    trigger_type: NotificationTriggerType
    project_id: str
    task_id: str | None = None
    title: str
    details: dict[str, Any] = Field(default_factory=dict)
    risk_class: RiskClass = Field(default=RiskClass.LOW)
    recipient_role: str = Field(default="founder")  # founder, client


class NotificationDecision(BaseModel):
    channel: NotificationChannel
    is_urgent: bool
    should_call_agentline: bool
    recipient_role: str
    reason: str
    summary: str


class NotificationPolicyEvaluator:
    """Evaluates notification events against strict channel policies."""

    @staticmethod
    def evaluate(event: NotificationEvent) -> NotificationDecision:
        """
        Routes routine reports to the portal, and initiates AgentLine voice calls
        strictly for verified urgent triggers.
        """
        if event.trigger_type in URGENT_CALL_TRIGGERS:
            # Urgent triggers require AgentLine outbound calling
            reason = (
                f"Urgent trigger '{event.trigger_type.value}' requires immediate voice notification"
            )
            return NotificationDecision(
                channel=NotificationChannel.AGENTLINE_CALL,
                is_urgent=True,
                should_call_agentline=True,
                recipient_role=event.recipient_role,
                reason=reason,
                summary=f"URGENT: {event.title}",
            )

        # All routine events stay inside portal
        return NotificationDecision(
            channel=NotificationChannel.PORTAL,
            is_urgent=False,
            should_call_agentline=False,
            recipient_role=event.recipient_role,
            reason=f"Routine event '{event.trigger_type.value}' routed to dashboard portal",
            summary=f"Update: {event.title}",
        )


notification_policy = NotificationPolicyEvaluator()
