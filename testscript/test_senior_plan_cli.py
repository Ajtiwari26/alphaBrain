"""CLI integration uses a signed model-double plan, never a live approval bypass."""

import json

import pytest

from alpha_core.planning.senior_planning_engine import SeniorPlanningEngine
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_core.triage_cli import main
from alpha_protocol.planning import ResearchSnapshot, request_digest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    queue = TaskTriageQueue(tmp_path / "queue.db", tmp_path / "stop.lock")
    envelope = {
        "objective": "Update bounded docs",
        "project_id": "project",
        "repo": "local",
        "base_commit": "a" * 40,
        "allowed_paths": ["TODO.md"],
    }
    queue.enqueue_task(
        "task",
        envelope,
        TaskProvenance("m", "s", 0, "test", "test", 1, "e", 0, request_digest(envelope)),
    )
    snapshot = ResearchSnapshot(
        task_id="task",
        project_id="project",
        repository_identity="local",
        base_sha="a" * 40,
        request_digest=request_digest(envelope),
        retrieval_time=1,
    )
    path = tmp_path / "snapshot.json"
    path.write_text(snapshot.model_dump_json())
    from alpha_core.planning.research_broker import ResearchBroker

    monkeypatch.setattr(ResearchBroker, "__init__", lambda self: None)
    args = ["--db-path", str(queue.db_path), "--emergency-lock", str(queue.emergency_lock_path)]
    return queue, args, path


def test_cli_attaches_plan_without_approval(setup, monkeypatch, capsys):
    queue, args, path = setup

    def invoke(self, model, prompt, schema):
        if "gemini" in model:
            return {
                "requirements": ["Document change"],
                "alternatives_considered": ["No change"],
                "chosen_design": "One bounded edit",
                "file_scope": ["TODO.md"],
            }
        return {"verdict": "APPROVE", "findings": "Sound bounded plan"}

    monkeypatch.setattr(SeniorPlanningEngine, "_invoke_agy_planning", invoke)
    assert main([*args, "senior-plan", "task", "--snapshot", str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "planned_pending_approval"
    assert queue.get_task("task")["status"] == "pending_review"
    assert queue.lease_next_approved_task("worker") is None
    assert queue.approve_task("task")


def test_cli_planning_failure_preserves_request(setup, monkeypatch):
    queue, args, path = setup
    before = queue.get_task("task")["envelope"]

    def fail(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(SeniorPlanningEngine, "_invoke_agy_planning", fail)
    assert main([*args, "senior-plan", "task", "--snapshot", str(path)]) == 2
    assert queue.get_task("task")["envelope"] == before
    with pytest.raises(ValueError):
        queue.approve_task("task")


def test_cli_approval_missing_plan_does_not_crash(setup, capsys):
    queue, args, _ = setup
    assert main([*args, "approve", "task"]) == 2
    assert "senior-plan" in capsys.readouterr().err
    assert queue.get_task("task")["status"] == "pending_review"


def test_safety_missing_plan_escalates_without_mutation(setup):
    from alpha_core.safety.gate import SafetyGate

    queue, _, _ = setup
    verdict = SafetyGate().review_task("task", queue)
    assert not verdict.passed and verdict.verdict == "ESCALATE"
    assert queue.get_task("task")["status"] == "pending_review"
