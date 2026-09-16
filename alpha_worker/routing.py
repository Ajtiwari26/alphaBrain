import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from alpha_core.config import settings
from alpha_protocol.routing import (
    ComplexityGateConfig,
    ExecutionStage,
    ModelTier,
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingRequest,
)

logger = logging.getLogger("alpha_worker.routing")


@dataclass
class ComplexityEvaluation:
    """Outcome of a ComplexityGate evaluation."""

    is_escalated: bool
    original_tier: str
    target_tier: str
    target_model: str
    complexity_class: str
    risk_class: str
    confidence_score: float
    rationale: list[str] = field(default_factory=list)


class ComplexityGate:
    """
    Evaluates task envelopes, routing requests, and research queries to deterministically
    select or escalate execution model tiers across the Tri-Tier Model Routing Topology.
    """

    TIER_1_MODEL = "gemini-3.8-flash-high"
    TIER_2_MODEL = "gemini-3.1-pro-high"
    TIER_3_MODEL_CLAUDE = "claude-opus-4-6-thinking"
    TIER_3_MODEL_PRO = "gemini-3.1-pro-high"

    def __init__(
        self,
        config: ComplexityGateConfig | None = None,
        tier_1_model: str | None = None,
        tier_2_model: str | None = None,
        tier_3_model: str | None = None,
        confidence_escalation_threshold: float | None = None,
        confidence_acceleration_threshold: float | None = None,
    ) -> None:
        self.config = config or ComplexityGateConfig()
        self.tier_1_model = tier_1_model or self.config.tier_1_model
        self.tier_2_model = tier_2_model or self.config.tier_2_model
        self.tier_3_model = tier_3_model or self.config.tier_3_model_claude
        self.confidence_escalation_threshold = (
            confidence_escalation_threshold
            if confidence_escalation_threshold is not None
            else self.config.confidence_escalation_threshold
        )
        self.confidence_acceleration_threshold = (
            confidence_acceleration_threshold
            if confidence_acceleration_threshold is not None
            else self.config.confidence_acceleration_threshold
        )
        self.sensitive_path_patterns = tuple(self.config.sensitive_path_patterns)

    def check_sensitive_paths(self, paths: list[str]) -> bool:
        """Checks if any path intersects with sensitive architectural/security boundaries."""
        for p in paths:
            low = p.lower()
            if any(pattern in low for pattern in self.sensitive_path_patterns):
                return True
        return False

    def should_escalate(
        self,
        complexity_class: str,
        risk_class: str,
        confidence_score: float | None = None,
        paths: list[str] | None = None,
    ) -> bool:
        """Determines if a task or query requires escalation to Tier 3 reasoning."""
        if risk_class.lower() in ("critical", "high"):
            return True
        if complexity_class.lower() in ("high", "extreme", "complex"):
            return True
        if confidence_score is not None and confidence_score < self.confidence_escalation_threshold:
            return True
        if paths and self.check_sensitive_paths(paths):
            return True
        return False

    def evaluate(
        self,
        envelope_or_request: dict[str, Any] | RoutingRequest,
        confidence_score: float | None = None,
        claude_budget_allowed: bool = False,
    ) -> ComplexityEvaluation:
        """
        Deterministically evaluates task envelope or routing request to select appropriate tier.
        """
        if isinstance(envelope_or_request, dict):
            risk_class = str(envelope_or_request.get("risk_class", "low"))
            complexity_class = str(envelope_or_request.get("complexity_class", "medium"))
            allowed_paths = envelope_or_request.get("allowed_paths", [])
            conf = confidence_score
            if conf is None:
                for k in ("extraction_confidence", "confidence_score", "confidence"):
                    if k in envelope_or_request and envelope_or_request[k] is not None:
                        try:
                            conf = float(envelope_or_request[k])
                            break
                        except (ValueError, TypeError):
                            pass
            if conf is None:
                conf = 0.85
        elif isinstance(envelope_or_request, RoutingRequest):
            risk_class = envelope_or_request.risk_class
            complexity_class = envelope_or_request.complexity_class
            allowed_paths = []
            conf = confidence_score if confidence_score is not None else 0.85
            claude_budget_allowed = envelope_or_request.claude_budget_allowed
        else:
            risk_class = getattr(envelope_or_request, "risk_class", "low")
            complexity_class = getattr(envelope_or_request, "complexity_class", "medium")
            allowed_paths = getattr(envelope_or_request, "allowed_paths", [])
            conf = confidence_score if confidence_score is not None else 0.85

        rationale: list[str] = []
        is_escalated = False

        low_comp = complexity_class.lower()
        if low_comp in ("low", "trivial", "mechanical"):
            original_tier = ModelTier.TIER_1_FAST.value
        elif low_comp in ("high", "extreme", "complex"):
            original_tier = ModelTier.TIER_3_REASONING.value
        else:
            original_tier = ModelTier.TIER_2_STANDARD.value

        target_tier = original_tier

        if risk_class.lower() in ("critical", "high"):
            is_escalated = True
            target_tier = ModelTier.TIER_3_REASONING.value
            rationale.append(f"escalated_risk_{risk_class.lower()}")

        if self.check_sensitive_paths(allowed_paths):
            is_escalated = True
            target_tier = ModelTier.TIER_3_REASONING.value
            rationale.append("escalated_sensitive_path_boundary")

        if conf < self.confidence_escalation_threshold:
            is_escalated = True
            target_tier = ModelTier.TIER_3_REASONING.value
            rationale.append(f"escalated_low_confidence_{conf:.2f}")
        elif (
            conf >= self.confidence_acceleration_threshold
            and not is_escalated
            and risk_class.lower() == "low"
            and low_comp in ("low", "trivial", "mechanical", "medium")
        ):
            if original_tier == ModelTier.TIER_2_STANDARD.value and low_comp == "low":
                target_tier = ModelTier.TIER_1_FAST.value
                rationale.append(f"accelerated_high_confidence_{conf:.2f}")

        if not rationale:
            rationale.append(f"standard_routing_{target_tier}")

        if target_tier == ModelTier.TIER_1_FAST.value:
            target_model = self.tier_1_model
        elif target_tier == ModelTier.TIER_3_REASONING.value:
            target_model = (
                self.tier_3_model if claude_budget_allowed else self.TIER_3_MODEL_PRO
            )
        else:
            target_model = self.tier_2_model

        return ComplexityEvaluation(
            is_escalated=is_escalated or (target_tier == ModelTier.TIER_3_REASONING.value and original_tier != ModelTier.TIER_3_REASONING.value),
            original_tier=original_tier,
            target_tier=target_tier,
            target_model=target_model,
            complexity_class=complexity_class,
            risk_class=risk_class,
            confidence_score=conf,
            rationale=rationale,
        )

    def escalate_request(self, request: RoutingRequest) -> RoutingRequest:
        """Deterministically escalates a RoutingRequest if criteria met."""
        eval_res = self.evaluate(request)
        if eval_res.is_escalated and eval_res.target_tier == ModelTier.TIER_3_REASONING.value:
            return request.model_copy(
                update={
                    "complexity_class": "high",
                    "allowed_models": [eval_res.target_model],
                }
            )
        return request


def call_model_router(request: RoutingRequest) -> RoutingDecision:
    """
    Calls the external alphabrain-model-router selector CLI.
    This respects the boundary: it does not switch accounts or make network calls.
    """
    gate = ComplexityGate()
    eval_res = gate.evaluate(request)

    if not settings.MODEL_ROUTING_ENABLED:
        model = (
            eval_res.target_model
            if request.stage == ExecutionStage.RESEARCH
            else settings.ANTIGRAVITY_MODEL
        )
        effort = (
            "high"
            if eval_res.target_tier == ModelTier.TIER_3_REASONING.value
            else settings.ANTIGRAVITY_EFFORT
        )
        return RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model=model,
            effort=effort,
            account_id="legacy_default",
            rationale_codes=["legacy_fallback", *eval_res.rationale],
            tier=eval_res.target_tier,
            confidence_score=eval_res.confidence_score,
        )

    # In a real environment, this invokes the skill CLI via python.
    # For testing, we mock or use the configured script path.
    # The selector expects --request <json> and --state <json>
    router_script = (
        Path.home()
        / ".gemini"
        / "config"
        / "skills"
        / "alphabrain-model-router"
        / "scripts"
        / "model_router.py"
    )

    if not router_script.exists():
        logger.warning(f"Router script not found at {router_script}, falling back to legacy")
        model = (
            eval_res.target_model
            if request.stage == ExecutionStage.RESEARCH
            else settings.ANTIGRAVITY_MODEL
        )
        effort = (
            "high"
            if eval_res.target_tier == ModelTier.TIER_3_REASONING.value
            else settings.ANTIGRAVITY_EFFORT
        )
        return RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model=model,
            effort=effort,
            account_id="legacy_default",
            rationale_codes=["missing_script_fallback", *eval_res.rationale],
            tier=eval_res.target_tier,
            confidence_score=eval_res.confidence_score,
        )

    req_json = request.model_dump_json()

    # We use a temporary file for the request to avoid command-line length limits or escaping issues
    import os
    import tempfile

    fd, req_path = tempfile.mkstemp(suffix=".json", prefix="agy_route_req_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(req_json)

        cmd = [
            "python3",
            str(router_script),
            "select",
            "--request",
            req_path,
            "--state",
            str(settings.ROUTER_STATE_PATH),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            logger.error(f"Router script failed (exit {result.returncode}): {result.stderr}")
            return RoutingDecision(
                status=RoutingDecisionStatus.BLOCKED, rationale_codes=["router_script_failed"]
            )

        try:
            decision_data = json.loads(result.stdout)
            if "tier" not in decision_data or not decision_data["tier"]:
                decision_data["tier"] = eval_res.target_tier
            if "confidence_score" not in decision_data or decision_data["confidence_score"] is None:
                decision_data["confidence_score"] = eval_res.confidence_score
            from typing import cast

            return cast(RoutingDecision, RoutingDecision.model_validate(decision_data))
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse router output: {e}\nOutput was: {result.stdout}")
            return RoutingDecision(
                status=RoutingDecisionStatus.BLOCKED, rationale_codes=["invalid_router_output"]
            )
    finally:
        os.remove(req_path)


def report_model_outcome(account_id: str, model: str, status: str) -> None:
    """Records the outcome of an execution attempt back into the routing state."""
    if not settings.MODEL_ROUTING_ENABLED:
        return

    router_script = (
        Path.home()
        / ".gemini"
        / "config"
        / "skills"
        / "alphabrain-model-router"
        / "scripts"
        / "model_router.py"
    )
    if not router_script.exists():
        return

    event_data = {
        "account": account_id,
        "model": model,
        "status": status,
    }

    import os
    import tempfile

    fd, evt_path = tempfile.mkstemp(suffix=".json", prefix="agy_route_evt_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(event_data))

        cmd = [
            "python3",
            str(router_script),
            "record",
            "--event",
            evt_path,
            "--state",
            str(settings.ROUTER_STATE_PATH),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(f"Failed to record model outcome: {result.stderr}")
    finally:
        os.remove(evt_path)
