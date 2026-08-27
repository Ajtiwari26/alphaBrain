import pytest
from pydantic import ValidationError

from alpha_core.config import settings
from alpha_protocol import (
    AccountModelState,
    AccountState,
    ExecutionStage,
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingRequest,
)
from alpha_worker.routing import call_model_router


def test_execution_stage_enum():
    assert ExecutionStage.PLAN.value == "plan"
    assert ExecutionStage.IMPLEMENT.value == "implement"
    assert ExecutionStage.REVIEW.value == "review"
    assert ExecutionStage.QA.value == "qa"
    assert ExecutionStage.MECHANICAL.value == "mechanical"


def test_routing_request_validation():
    req = RoutingRequest(
        project_id="prj_1",
        task_id="tsk_1",
        attempt_id="att_1",
        stage=ExecutionStage.IMPLEMENT,
        risk_class="high",
        complexity_class="medium",
    )
    assert req.stage == ExecutionStage.IMPLEMENT
    assert req.claude_budget_allowed is False


def test_routing_request_invalid_stage():
    with pytest.raises(ValidationError):
        RoutingRequest(
            project_id="prj_1",
            task_id="tsk_1",
            attempt_id="att_1",
            stage="invalid_stage",
            risk_class="high",
            complexity_class="medium",
        )


def test_routing_decision():
    dec = RoutingDecision(
        status=RoutingDecisionStatus.SELECTED,
        model="gemini-3.1-pro-high",
        account_id="fake_account",
    )
    assert dec.status == RoutingDecisionStatus.SELECTED
    assert dec.model == "gemini-3.1-pro-high"
    assert dec.founder_review_required is False


def test_account_model_state():
    state = AccountModelState(state=AccountState.AVAILABLE, rolling_successes=5)
    assert state.state == AccountState.AVAILABLE
    assert state.rolling_successes == 5


def test_call_model_router_disabled():
    # If disabled, returns legacy
    settings.MODEL_ROUTING_ENABLED = False
    req = RoutingRequest(
        project_id="prj_1",
        task_id="tsk_1",
        attempt_id="att_1",
        stage=ExecutionStage.IMPLEMENT,
        risk_class="high",
        complexity_class="medium",
    )
    decision = call_model_router(req)
    assert decision.status == RoutingDecisionStatus.SELECTED
    assert decision.account_id == "legacy_default"
    assert decision.model == settings.ANTIGRAVITY_MODEL
    assert "legacy_fallback" in decision.rationale_codes


def test_call_model_router_missing_script(monkeypatch):
    settings.MODEL_ROUTING_ENABLED = True

    # Mock Path.exists to return False for the router script
    import pathlib

    original_exists = pathlib.Path.exists

    def mock_exists(self):
        if "model_router.py" in self.name:
            return False
        return original_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", mock_exists)

    # ensure it falls back if script missing
    req = RoutingRequest(
        project_id="prj_1",
        task_id="tsk_1",
        attempt_id="att_1",
        stage=ExecutionStage.IMPLEMENT,
        risk_class="high",
        complexity_class="medium",
    )

    decision = call_model_router(req)
    assert decision.status == RoutingDecisionStatus.SELECTED
    assert decision.account_id == "legacy_default"
    assert "missing_script_fallback" in decision.rationale_codes
