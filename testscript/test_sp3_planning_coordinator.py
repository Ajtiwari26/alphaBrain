"""
Tests for SP3 Senior Planning Coordinator engine.
Ensures Pro/Opus agreement, timeouts, and blueprint binding.
"""

import hashlib
import json
import pytest
from unittest.mock import MagicMock

from alpha_protocol.planning import PlanAssessment, PlanBlueprint, ResearchSnapshot
from alpha_core.planning.senior_planning_engine import SeniorPlanningEngine, PlanningConsensusError


def test_senior_planning_engine_success(monkeypatch):
    queue_mock = MagicMock()
    queue_mock.get_task.return_value = {
        "id": "tsk_123",
        "objective": "Build the research broker",
        "project_id": "proj_1",
        "repo": "alphaBrain"
    }

    broker_mock = MagicMock()

    engine = SeniorPlanningEngine(
        queue=queue_mock,
        research_broker=broker_mock,
        signing_secret="supersecret"
    )

    def mock_invoke(model, prompt, schema, **kwargs):
        if "gemini" in model:
            return {
                "requirements": ["Req 1"],
                "alternatives_considered": ["Alt 1"],
                "chosen_design": "Design 1",
                "file_scope": ["file1.py"],
                "token_budgets": {"draft": 1000}
            }
        elif "opus" in model:
            return {
                "findings": "Looks good.",
                "verdict": "APPROVE"
            }
        raise ValueError(f"Unknown model: {model}")

    monkeypatch.setattr(engine, "_invoke_agy_planning", mock_invoke)

    snapshot = ResearchSnapshot(
        task_id="tsk_123",
        project_id="proj_1",
        repository_identity="alphaBrain",
        base_sha="abcd1234abcd1234abcd1234abcd1234abcd1234",
        request_digest="a"*64,
        retrieval_time=1234567890.0,
    )

    attestation, blueprint = engine.execute_planning_phase("tsk_123", snapshot)

    assert blueprint.task_id == "tsk_123"
    assert blueprint.chosen_design == "Design 1"
    
    assert attestation.blueprint_digest == blueprint.compute_digest()
    assert attestation.pro_assessment.verdict == "APPROVE"
    assert attestation.opus_assessment.verdict == "APPROVE"
    assert attestation.verify("supersecret") is True


def test_senior_planning_engine_opus_rejection(monkeypatch):
    queue_mock = MagicMock()
    queue_mock.get_task.return_value = {
        "id": "tsk_123",
        "objective": "Build the research broker",
        "project_id": "proj_1",
        "repo": "alphaBrain"
    }

    broker_mock = MagicMock()

    engine = SeniorPlanningEngine(
        queue=queue_mock,
        research_broker=broker_mock,
        signing_secret="supersecret"
    )

    def mock_invoke(model, prompt, schema, **kwargs):
        if "gemini" in model:
            return {
                "requirements": ["Req 1"],
                "alternatives_considered": ["Alt 1"],
                "chosen_design": "Design 1",
                "file_scope": ["file1.py"]
            }
        elif "opus" in model:
            return {
                "findings": "Design has an SSRF vulnerability.",
                "verdict": "REPAIR_REQUIRED"
            }
        raise ValueError(f"Unknown model: {model}")

    monkeypatch.setattr(engine, "_invoke_agy_planning", mock_invoke)

    snapshot = ResearchSnapshot(
        task_id="tsk_123",
        project_id="proj_1",
        repository_identity="alphaBrain",
        base_sha="abcd1234abcd1234abcd1234abcd1234abcd1234",
        request_digest="a"*64,
        retrieval_time=1234567890.0,
    )

    with pytest.raises(PlanningConsensusError, match="Opus rejected the plan"):
        engine.execute_planning_phase("tsk_123", snapshot)


def test_senior_planning_engine_timeout_quota_failure(monkeypatch):
    queue_mock = MagicMock()
    queue_mock.get_task.return_value = {
        "id": "tsk_123",
        "objective": "Do work",
    }
    broker_mock = MagicMock()
    engine = SeniorPlanningEngine(queue=queue_mock, research_broker=broker_mock, signing_secret="secret")

    def mock_invoke(*args, **kwargs):
        raise RuntimeError("Model invocation failed: quota exceeded or timeout")

    monkeypatch.setattr(engine, "_invoke_agy_planning", mock_invoke)

    snapshot = ResearchSnapshot(
        task_id="tsk_123",
        project_id="proj_1",
        repository_identity="alphaBrain",
        base_sha="abcd1234abcd1234abcd1234abcd1234abcd1234",
        request_digest="a"*64,
        retrieval_time=123.0
    )

    with pytest.raises(PlanningConsensusError, match="Pro Draft failed: Model invocation failed: quota exceeded or timeout"):
        engine.execute_planning_phase("tsk_123", snapshot)
