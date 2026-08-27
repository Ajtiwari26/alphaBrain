import json
import logging
import subprocess
from pathlib import Path

from pydantic import ValidationError

from alpha_core.config import settings
from alpha_protocol import RoutingDecision, RoutingDecisionStatus, RoutingRequest

logger = logging.getLogger("alpha_worker.routing")


def call_model_router(request: RoutingRequest) -> RoutingDecision:
    """
    Calls the external alphabrain-model-router selector CLI.
    This respects the boundary: it does not switch accounts or make network calls.
    """
    if not settings.MODEL_ROUTING_ENABLED:
        return RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model=settings.ANTIGRAVITY_MODEL,
            effort=settings.ANTIGRAVITY_EFFORT,
            account_id="legacy_default",
            rationale_codes=["legacy_fallback"],
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
        return RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model=settings.ANTIGRAVITY_MODEL,
            effort=settings.ANTIGRAVITY_EFFORT,
            account_id="legacy_default",
            rationale_codes=["missing_script_fallback"],
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
