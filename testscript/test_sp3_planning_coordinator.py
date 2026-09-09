"""Planning uses real queue shape and strict AGY structured responses."""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from alpha_core.planning.senior_planning_engine import PlanningConsensusError, SeniorPlanningEngine
from alpha_protocol.planning import ResearchSnapshot, request_digest


@pytest.fixture
def context():
    envelope = {
        "objective": "Build research broker",
        "project_id": "proj_1",
        "repo": "alphaBrain",
        "base_commit": "a" * 40,
        "allowed_paths": ["file1.py"],
    }
    queue = MagicMock()
    queue.get_task.return_value = {"id": "tsk_123", "envelope": envelope}
    engine = SeniorPlanningEngine(queue, MagicMock(), signing_secret=b"test-secret")
    snapshot = ResearchSnapshot(
        task_id="tsk_123",
        project_id="proj_1",
        repository_identity="alphaBrain",
        base_sha="a" * 40,
        request_digest=request_digest(envelope),
        retrieval_time=123,
    )
    return engine, snapshot


def draft():
    return {
        "requirements": ["Req 1"],
        "alternatives_considered": ["Alt 1"],
        "chosen_design": "Design 1",
        "file_scope": ["file1.py"],
    }


def test_success_uses_nested_task_metadata(context, monkeypatch):
    engine, snapshot = context

    def invoke(model, prompt, schema):
        assert "Build research broker" in prompt and "proj_1" in prompt
        return draft() if "gemini" in model else {"verdict": "APPROVE", "findings": "Valid design"}

    monkeypatch.setattr(engine, "_invoke_agy_planning", invoke)
    att, bp = engine.execute_planning_phase("tsk_123", snapshot)
    assert att.verify("test-secret")
    assert att.project_id == "proj_1" and att.repository_identity == "alphaBrain"
    assert att.blueprint_digest == bp.compute_digest()


def test_opus_rejection(context, monkeypatch):
    engine, snapshot = context
    monkeypatch.setattr(
        engine,
        "_invoke_agy_planning",
        lambda model, *_: (
            draft()
            if "gemini" in model
            else {"verdict": "REPAIR_REQUIRED", "findings": "SSRF risk"}
        ),
    )
    with pytest.raises(PlanningConsensusError, match="Opus rejected"):
        engine.execute_planning_phase("tsk_123", snapshot)


def test_quota_or_timeout_does_not_attest(context, monkeypatch):
    engine, snapshot = context
    invoke = MagicMock(side_effect=RuntimeError("quota exhausted"))
    monkeypatch.setattr(engine, "_invoke_agy_planning", invoke)
    with pytest.raises(PlanningConsensusError, match="Pro Draft failed"):
        engine.execute_planning_phase("tsk_123", snapshot)
    assert invoke.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"structured_output": draft()},
        {**draft(), "requirements": []},
        {**draft(), "file_scope": ["outside.py"]},
    ],
)
def test_invalid_draft_blocks_before_critique(context, monkeypatch, payload):
    engine, snapshot = context
    invoke = MagicMock(return_value=payload)
    monkeypatch.setattr(engine, "_invoke_agy_planning", invoke)
    with pytest.raises(PlanningConsensusError):
        engine.execute_planning_phase("tsk_123", snapshot)
    assert invoke.call_count == 1


def test_stale_research_rejected_before_model(context, monkeypatch):
    engine, snapshot = context
    invoke = MagicMock()
    monkeypatch.setattr(engine, "_invoke_agy_planning", invoke)
    snapshot.request_digest = "c" * 64
    with pytest.raises(ValueError, match="does not match"):
        engine.execute_planning_phase("tsk_123", snapshot)
    invoke.assert_not_called()


@pytest.mark.parametrize(
    "stdout",
    [
        "[]",
        "{} trailing",
        '{"x":1,"x":2}',
        '{"structured_output":null}',
        '{"is_error":true,"structured_output":{}}',
    ],
)
def test_response_protocol_rejects_ambiguity(stdout):
    with pytest.raises(ValueError):
        SeniorPlanningEngine._parse_response(stdout)


def test_structured_output_extracted_and_secrets_not_inherited(context, monkeypatch, tmp_path):
    engine, _ = context
    engine.agy_bin = tmp_path / "agy"
    engine.agy_bin.touch()
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_production_v1", "must-not-reach-model")
    monkeypatch.setenv("DATABASE_URL", "private")

    def run(cmd, **kwargs):
        assert "DATABASE_URL" not in kwargs["env"]
        assert not any(k.startswith("ALPHA_SIGNING_SECRET") for k in kwargs["env"])
        assert "--dangerously-skip-permissions" not in cmd
        assert "--sandbox" in cmd
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"structured_output": draft()}), "")

    monkeypatch.setattr(subprocess, "run", run)
    assert engine._invoke_agy_planning("pro", "prompt", {}) == draft()
