"""Real planning signatures; corruption confined to temporary SQLite fixtures."""

import json
import os
import sqlite3
import time

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_protocol.planning import PlanningAttestation, request_digest
from testscript.planning_fixtures import attach_test_plan, plan_for_task


@pytest.fixture
def queue(tmp_path):
    queue = TaskTriageQueue(str(tmp_path / "triage.db"), str(tmp_path / "stop.lock"))
    envelope = {"objective": "Test planning", "base_commit": "a" * 40, "allowed_paths": ["TODO.md"]}
    provenance = TaskProvenance("m", "s", 0, "test", "test", 1, "e", 0, request_digest(envelope))
    queue.enqueue_task("task", envelope, provenance)
    return queue


def test_approve_without_plan_fails(queue):
    with pytest.raises(ValueError, match="without a valid PlanningAttestation"):
        queue.approve_task("task")


def test_signed_plan_lifecycle(queue):
    attach_test_plan(queue, "task")
    assert queue.approve_task("task")
    assert queue.lease_next_approved_task("worker")["id"] == "task"


@pytest.mark.parametrize(
    "field,value",
    [
        ("signature", "a" * 64),
        ("task_id", "other"),
        ("project_id", "other"),
        ("repository_identity", "other"),
        ("base_sha", "b" * 40),
        ("policy_version", "weakened"),
        ("issuer", "impostor"),
        ("expires_at", 0),
    ],
)
def test_attestation_tampering_rejected(queue, field, value):
    att, bp = plan_for_task(queue, "task")
    att[field] = value
    with pytest.raises(ValueError):
        queue.attach_plan("task", att, bp)
    assert queue.get_task("task")["status"] == "pending_review"


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer_principal", "impostor"),
        ("findings", "rewritten"),
        ("plan_digest", "c" * 64),
        ("role", "drafting"),
        ("verdict", "BLOCKED"),
    ],
)
def test_reviewer_fields_are_signed(queue, field, value):
    att, bp = plan_for_task(queue, "task")
    att["opus_assessment"][field] = value
    with pytest.raises(ValueError):
        queue.attach_plan("task", att, bp)


def test_blueprint_tampering_rejected_at_attach(queue):
    att, bp = plan_for_task(queue, "task")
    bp["chosen_design"] = "malicious design"
    with pytest.raises(ValueError, match="digest does not match"):
        queue.attach_plan("task", att, bp)


@pytest.mark.parametrize("phase", ["approval", "lease"])
@pytest.mark.parametrize(
    "column,value",
    [
        ("planning_attestation_json", None),
        ("plan_blueprint_json", None),
        ("plan_blueprint_json", "{}"),
        ("envelope_json", '{"objective":"changed"}'),
    ],
)
def test_revalidate_persisted_state_on_every_boundary(queue, phase, column, value):
    attach_test_plan(queue, "task")
    if phase == "lease":
        assert queue.approve_task("task")
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(f"UPDATE task_triage_queue SET {column} = ? WHERE id = ?", (value, "task"))
    with pytest.raises(ValueError):
        queue.approve_task("task") if phase == "approval" else queue.lease_next_approved_task(
            "worker"
        )


def test_cannot_replace_approved_plan(queue):
    att, bp = plan_for_task(queue, "task")
    assert queue.attach_plan("task", att, bp)
    assert queue.approve_task("task")
    assert not queue.attach_plan("task", att, bp)
    assert not queue.attach_plan("missing", att, bp)


def test_expiry_rechecked_at_lease(queue, monkeypatch):
    att, bp = plan_for_task(queue, "task")
    assert queue.attach_plan("task", att, bp)
    assert queue.approve_task("task")
    monkeypatch.setattr(time, "time", lambda: att["expires_at"])
    with pytest.raises(ValueError, match="expired"):
        queue.lease_next_approved_task("worker")


def test_request_binding_rejects_changed_objective(queue):
    att, bp = plan_for_task(queue, "task")
    env = queue.get_task("task")["envelope"]
    env["objective"] = "Different request"
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET envelope_json = ? WHERE id = ?", (json.dumps(env), "task")
        )
    with pytest.raises(ValueError, match="request digest mismatch"):
        queue.attach_plan("task", att, bp)


def test_no_fallback_for_unconfigured_key(queue, monkeypatch):
    att, bp = plan_for_task(queue, "task")
    monkeypatch.delenv("ALPHA_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("ALPHA_SIGNING_SECRET_alpha_production_v1", raising=False)
    with pytest.raises(ValueError, match="key is unavailable"):
        queue.attach_plan("task", att, bp)


def test_signature_survives_json_roundtrip(queue):
    att, _ = plan_for_task(queue, "task")
    assert PlanningAttestation.model_validate_json(json.dumps(att)).verify(
        os.environ["ALPHA_SIGNING_SECRET"]
    )
