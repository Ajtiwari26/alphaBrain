"""
Alpha Brain Action Broker
=========================
Typed deny-by-default action broker enforcing human approvals for high-risk,
destructive, deployment, migration, DNS, financial, and external communication actions.
"""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from alpha_protocol.enums import RiskClass


class ActionType(str, Enum):
    SHELL_EXEC = "shell_exec"
    FILE_WRITE = "file_write"
    BROWSER_ACTION = "browser_action"
    PRODUCTION_DEPLOYMENT = "production_deployment"
    DATABASE_MIGRATION = "database_migration"
    DNS_CHANGE = "dns_change"
    DESTRUCTIVE_COMMAND = "destructive_command"
    PAYMENT = "payment"
    EXTERNAL_COMMUNICATION = "external_communication"
    MCP_TOOL = "mcp_tool"


HUMAN_APPROVAL_REQUIRED_ACTIONS = frozenset(
    {
        ActionType.PRODUCTION_DEPLOYMENT,
        ActionType.DATABASE_MIGRATION,
        ActionType.DNS_CHANGE,
        ActionType.DESTRUCTIVE_COMMAND,
        ActionType.PAYMENT,
        ActionType.EXTERNAL_COMMUNICATION,
    }
)

DESTRUCTIVE_PATTERNS = (
    re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--force|--recursive)\b", re.IGNORECASE),
    re.compile(r"\b(mkfs|dd\s+if=|fdisk|parted)\b", re.IGNORECASE),
    re.compile(r"\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE)\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # Fork bomb
)


class ActionRequest(BaseModel):
    action_type: ActionType
    target: str = Field(description="Target file, domain, command, or resource identifier")
    command_or_params: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(description="Worker ID or agent identity proposing the action")
    risk_class: RiskClass = Field(default=RiskClass.LOW)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionDecision(BaseModel):
    allowed: bool
    requires_human_approval: bool
    reason: str
    action_type: ActionType
    approver: str | None = None


class ActionBroker:
    """Evaluates requested actions under a strict deny-by-default security policy."""

    @staticmethod
    def is_destructive_payload(command_str: str) -> bool:
        """Inspects shell commands and raw strings for destructive patterns."""
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern.search(command_str):
                return True
        return False

    def evaluate_action(
        self,
        request: ActionRequest,
        human_approval_granted: bool = False,
        approver: str | None = None,
    ) -> ActionDecision:
        """
        Evaluates an action request.
        Enforces human approvals for sensitive actions and rejects unknown/destructive payloads.
        """
        # 1. Detect if a regular shell/MCP command contains destructive operations
        effective_action_type = request.action_type
        if request.action_type in {ActionType.SHELL_EXEC, ActionType.MCP_TOOL}:
            raw_cmd = str(request.command_or_params.get("command") or request.target)
            if self.is_destructive_payload(raw_cmd):
                effective_action_type = ActionType.DESTRUCTIVE_COMMAND

        # 2. Check if the action requires human approval
        if effective_action_type in HUMAN_APPROVAL_REQUIRED_ACTIONS:
            if not human_approval_granted:
                return ActionDecision(
                    allowed=False,
                    requires_human_approval=True,
                    reason=f"Action '{effective_action_type.value}' requires explicit human approval",
                    action_type=effective_action_type,
                )
            if not approver:
                return ActionDecision(
                    allowed=False,
                    requires_human_approval=True,
                    reason="Human approval claimed but approver identity is missing",
                    action_type=effective_action_type,
                )
            return ActionDecision(
                allowed=True,
                requires_human_approval=True,
                reason=f"Approved by human operator '{approver}'",
                action_type=effective_action_type,
                approver=approver,
            )

        # 3. Critical risk class requires human approval regardless of action type
        if request.risk_class == RiskClass.CRITICAL:
            if not human_approval_granted:
                return ActionDecision(
                    allowed=False,
                    requires_human_approval=True,
                    reason="Actions with Critical risk class require explicit human approval",
                    action_type=effective_action_type,
                )
            return ActionDecision(
                allowed=True,
                requires_human_approval=True,
                reason=f"Critical risk action approved by human operator '{approver}'",
                action_type=effective_action_type,
                approver=approver,
            )

        # 4. Standard safe non-destructive actions are allowed
        if effective_action_type in {
            ActionType.SHELL_EXEC,
            ActionType.FILE_WRITE,
            ActionType.BROWSER_ACTION,
            ActionType.MCP_TOOL,
        }:
            return ActionDecision(
                allowed=True,
                requires_human_approval=False,
                reason="Action permitted under standard execution policy",
                action_type=effective_action_type,
            )

        # 5. Deny-by-default for any unhandled action type
        return ActionDecision(
            allowed=False,
            requires_human_approval=False,
            reason=f"Action type '{effective_action_type.value}' is denied by default",
            action_type=effective_action_type,
        )


action_broker = ActionBroker()
