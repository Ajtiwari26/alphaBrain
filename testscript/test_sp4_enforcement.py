"""
Tests for SP4 Execution and Safety Enforcement Pipeline.
Verifies that direct execution paths without planning are blocked.
"""

import json
import uuid
import pytest
import sqlite3
import hashlib
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus, TaskProvenance
from alpha_protocol.planning import PlanBlueprint, PlanningAttestation, PlanAssessment


def create_fake_attestation_and_blueprint(task_id: str, base_sha: str) -> tuple[dict, dict]:
    bp = PlanBlueprint(
        task_id=task_id,
        base_sha=base_sha,
        input_request_digest="a" * 64,
        research_snapshot_digest="b" * 64,
        requirements=[],
        alternatives_considered=[],
        chosen_design="test",
        file_scope=[]
    )
    
    blueprint_dict = json.loads(bp.model_dump_json())
    bp_digest = bp.compute_digest()
    
    att = PlanningAttestation(
        task_id=task_id,
        project_id="default",
        repository_identity="local",
        base_sha=base_sha,
        blueprint_digest=bp_digest,
        pro_assessment=PlanAssessment(
            reviewer_principal="pro",
            role="drafting",
            plan_digest=bp_digest,
            verdict="APPROVE",
            findings="ok"
        ),
        opus_assessment=PlanAssessment(
            reviewer_principal="opus",
            role="critique",
            plan_digest=bp_digest,
            verdict="APPROVE",
            findings="ok"
        ),
        key_id="test",
        issued_at=0.0,
        expires_at=0.0,
        signature="a" * 64
    )
    
    attestation_dict = json.loads(att.model_dump_json())
    return attestation_dict, blueprint_dict


def create_fake_provenance(envelope: dict[str, Any]) -> TaskProvenance:
    canonical_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return TaskProvenance(
        meeting_id="m1",
        speaker_id="s1",
        utterance_timestamp=0.0,
        transcript_excerpt="test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="e1",
        created_at=0.0,
        content_hash=canonical_hash
    )

def test_triage_queue_approve_fails_without_attestation(tmp_path):
    db_path = tmp_path / "triage.db"
    queue = TaskTriageQueue(str(db_path))
    
    base_sha = "a" * 40
    task_id = "tsk_" + uuid.uuid4().hex
    envelope = {"title": "Test", "base_commit": base_sha}
    prov = create_fake_provenance(envelope)
    queue.enqueue_task(task_id, envelope, prov)
    
    with pytest.raises(ValueError, match="cannot be approved without a valid PlanningAttestation"):
        queue.approve_task(task_id)


def test_triage_queue_approve_fails_on_stale_base_commit(tmp_path):
    db_path = tmp_path / "triage.db"
    queue = TaskTriageQueue(str(db_path))
    
    # Task base commit is all A's
    base_sha = "a" * 40
    task_id = "tsk_" + uuid.uuid4().hex
    envelope = {"title": "Test", "base_commit": base_sha}
    prov = create_fake_provenance(envelope)
    queue.enqueue_task(task_id, envelope, prov)
    
    # Fake plan with all B's (stale)
    stale_sha = "b" * 40
    att, bp = create_fake_attestation_and_blueprint(task_id, stale_sha)
    
    queue.attach_plan(task_id, att, bp)
    
    with pytest.raises(ValueError, match="Stale plan: task base_commit"):
        queue.approve_task(task_id)


def test_triage_queue_lease_fails_on_digest_mismatch(tmp_path):
    db_path = tmp_path / "triage.db"
    queue = TaskTriageQueue(str(db_path))
    
    base_sha = "a" * 40
    task_id = "tsk_" + uuid.uuid4().hex
    envelope = {"title": "Test", "base_commit": base_sha}
    prov = create_fake_provenance(envelope)
    queue.enqueue_task(task_id, envelope, prov)
    
    att, bp = create_fake_attestation_and_blueprint(task_id, base_sha)
    
    # Mutate blueprint
    bp["chosen_design"] = "malicious_design_change"
    queue.attach_plan(task_id, att, bp)
    
    queue.approve_task(task_id)
    
    with pytest.raises(ValueError, match="planning attestation digest does not match the blueprint"):
        queue.lease_next_approved_task("worker_1")
