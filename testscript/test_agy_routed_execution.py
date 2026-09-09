from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alpha_core.config import settings
from alpha_protocol import RoutingDecision, RoutingDecisionStatus
from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge
from testscript.test_antigravity_live_bridge import make_task


@pytest.fixture(autouse=True)
def isolated_routing_settings(monkeypatch):
    # These are routing unit tests with mocked AGY calls, not a live CLI/login
    # readiness proof. Restore settings so later tests cannot invoke routing.
    monkeypatch.setattr(settings, "MODEL_ROUTING_ENABLED", False)
    monkeypatch.setattr(settings, "ANTIGRAVITY_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "MAX_ELIGIBLE_ATTEMPTS", 2)
    monkeypatch.setattr(
        AntigravityLiveBridge, "check_readiness", lambda self: (True, "test double")
    )


@pytest.fixture
def mock_router():
    with patch("alpha_worker.adapters.antigravity_live.call_model_router") as mock:
        yield mock


@pytest.fixture
def mock_reporter():
    with patch("alpha_worker.adapters.antigravity_live.report_model_outcome") as mock:
        yield mock


@pytest.fixture
def mock_lease():
    # We need to mock acquire_credential_lease as an async context manager
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_acm(*args, **kwargs):
        yield MagicMock()

    with patch(
        "alpha_worker.adapters.antigravity_live.acquire_credential_lease", side_effect=mock_acm
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_feature_off_preserves_old_path(mock_router, mock_lease, tmp_path):
    settings.MODEL_ROUTING_ENABLED = False
    settings.ANTIGRAVITY_EXECUTION_ENABLED = True
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path

    # We shouldn't need to mock anything special because _run_agy is mocked to return success
    bridge._run_agy = AsyncMock(
        return_value={
            "returncode": 0,
            "events": [
                {
                    "event": "result",
                    "result": {
                        "conversation_id": "test",
                        "status": "SUCCESS",
                        "response": "ALPHA_BRAIN_QA_EVIDENCE:{}\nALPHA_BRAIN_TASK_DONE",
                    },
                }
            ],
        }
    )

    mock_router.return_value = RoutingDecision(
        status=RoutingDecisionStatus.SELECTED,
        model="legacy_model",
        effort="high",
        account_id="legacy_default",
    )

    task = make_task()
    dispatch = await bridge.dispatch(task, tmp_path, "att_1")

    assert mock_router.called
    assert not mock_lease.called
    assert (
        dispatch.completed is False
    )  # Since our fake JSON was bad, it doesn't matter, it didn't crash.


@pytest.mark.asyncio
async def test_429_exhausts_eligible_profiles(mock_router, mock_reporter, mock_lease, tmp_path):
    settings.MODEL_ROUTING_ENABLED = True
    settings.ANTIGRAVITY_EXECUTION_ENABLED = True
    settings.MAX_ELIGIBLE_ATTEMPTS = 2
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path

    bridge._run_agy = AsyncMock(return_value={"returncode": 429, "events": []})

    mock_router.side_effect = [
        RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model="gemini-3.1-pro-high",
            effort="high",
            account_id="acct_1",
        ),
        RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model="gemini-3.1-pro-high",
            effort="high",
            account_id="acct_2",
        ),
    ]

    task = make_task()
    dispatch = await bridge.dispatch(task, tmp_path, "att_1")

    assert dispatch.completed is False
    assert dispatch.blocked_reason == "exhausted eligible accounts via 429"

    # Should have called router twice
    assert mock_router.call_count == 2

    # Should have reported rate limit twice
    assert mock_reporter.call_count == 2
    mock_reporter.assert_any_call("acct_1", "gemini-3.1-pro-high", "rate_limit")
    mock_reporter.assert_any_call("acct_2", "gemini-3.1-pro-high", "rate_limit")


@pytest.mark.asyncio
async def test_auth_failure_blocks_dispatch(mock_router, mock_reporter, tmp_path):
    # Test that exception in lease causes blocked reason auth_failed
    settings.MODEL_ROUTING_ENABLED = True
    settings.ANTIGRAVITY_EXECUTION_ENABLED = True
    settings.MAX_ELIGIBLE_ATTEMPTS = 2
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path

    from contextlib import asynccontextmanager

    from alpha_worker.agy_credentials import SwitchCommandError

    @asynccontextmanager
    async def failing_lease(*args, **kwargs):
        raise SwitchCommandError("Failed auth")
        yield None

    with patch(
        "alpha_worker.adapters.antigravity_live.acquire_credential_lease", side_effect=failing_lease
    ):
        mock_router.return_value = RoutingDecision(
            status=RoutingDecisionStatus.SELECTED,
            model="gemini-3.1-pro-high",
            effort="high",
            account_id="acct_1",
        )

        task = make_task()
        dispatch = await bridge.dispatch(task, tmp_path, "att_1")

        assert dispatch.completed is False
        assert dispatch.blocked_reason == "auth_failed"
        mock_reporter.assert_called_with("acct_1", "gemini-3.1-pro-high", "auth_failed")
