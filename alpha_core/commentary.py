from typing import Any


class LiveCommentaryEngine:
    """
    Synthesizes technical execution states, gate checks, and review debates
    into concise, plain-English progress updates for business owners and founders.
    """

    def __init__(self) -> None:
        pass

    def translate_state_change(self, task_id: str, from_state: str, to_state: str) -> str:
        """Translates a transition between technical states."""
        state_map = {
            "queued": "waiting to start",
            "researching": "gathering initial context and documentation",
            "planning": "drafting an implementation plan",
            "executing": "actively writing code and applying changes",
            "reviewing": "undergoing senior engineering review",
            "testing": "running automated quality checks",
            "completed": "successfully finished and ready",
            "failed": "blocked by an issue that requires attention",
        }
        friendly_to = state_map.get(to_state.lower(), to_state.replace('_', ' '))
        return f"Task {task_id} is now {friendly_to}."

    def translate_gate_check(self, gate_name: str, passed: bool, error: str | None = None) -> str:
        """Translates a gate check result (e.g., unit tests, linting, security)."""
        friendly_gate = gate_name.replace('_', ' ').title()
        if passed:
            return f"Passed the {friendly_gate} quality check."
        else:
            reason = f" due to an issue: {error}" if error else "."
            return f"Did not pass the {friendly_gate} quality check{reason}"

    def translate_review_debate(self, reviewer: str, verdict: str, comments: str) -> str:
        """Translates the outcome of a senior review debate."""
        verdict_clean = verdict.strip().lower()
        if verdict_clean in ["approve", "approved", "pass"]:
            return f"{reviewer} approved the changes. Note: {comments}"
        elif verdict_clean in ["reject", "rejected", "fail", "repair"]:
            return f"{reviewer} requested revisions. Feedback: {comments}"
        else:
            return f"{reviewer} provided a review verdict of '{verdict}'. Note: {comments}"

    def translate_event(self, event_type: str, details: dict[str, Any]) -> str:
        """General dispatcher for arbitrary execution events."""
        if event_type == "state_change":
            return self.translate_state_change(
                task_id=details.get("task_id", "Unknown"),
                from_state=details.get("from_state", "unknown"),
                to_state=details.get("to_state", "unknown")
            )
        elif event_type == "gate_check":
            return self.translate_gate_check(
                gate_name=details.get("gate_name", "Unknown Gate"),
                passed=details.get("passed", False),
                error=details.get("error")
            )
        elif event_type == "review_debate":
            return self.translate_review_debate(
                reviewer=details.get("reviewer", "Reviewer"),
                verdict=details.get("verdict", "unknown"),
                comments=details.get("comments", "No comments provided.")
            )
        else:
            return f"System event occurred: {event_type.replace('_', ' ')}."
