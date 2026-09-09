"""Explicit signed plans for isolated queue tests; never use against live queues."""

import os
import re
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import DEFAULT_DB_PATH, TaskTriageQueue
from alpha_protocol.planning import (
    PlanAssessment,
    PlanBlueprint,
    PlanningAttestation,
    request_digest,
)


def plan_for_task(queue: TaskTriageQueue, task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    # This is test evidence, not a claim that a model independently reviewed code.
    assert os.environ.get("ENV") == "test"
    assert Path(queue.db_path).resolve() != DEFAULT_DB_PATH.resolve()
    task = queue.get_task(task_id)
    assert task is not None
    envelope = task["envelope"]
    base = str(envelope.get("base_commit", ""))
    bp = PlanBlueprint(
        task_id=task_id,
        base_sha=base.lower() if re.fullmatch(r"[a-fA-F0-9]{40}", base) else "a" * 40,
        input_request_digest=request_digest(envelope),
        research_snapshot_digest="b" * 64,
        requirements=["Exercise the test's existing queue lifecycle invariant"],
        alternatives_considered=["Reject without a signed test fixture"],
        chosen_design="Isolated deterministic test fixture",
        file_scope=envelope.get("allowed_paths", []),
    )
    digest = bp.compute_digest()
    att = PlanningAttestation.create(
        task_id=task_id,
        project_id=envelope.get("project_id", "default"),
        repository_identity=envelope.get("repo", "local"),
        base_sha=bp.base_sha,
        blueprint_digest=digest,
        pro_assessment=PlanAssessment(
            reviewer_principal="test-pro",
            role="drafting",
            plan_digest=digest,
            verdict="APPROVE",
            findings="Test fixture only",
        ),
        opus_assessment=PlanAssessment(
            reviewer_principal="test-opus",
            role="critique",
            plan_digest=digest,
            verdict="APPROVE",
            findings="Test fixture only",
        ),
        secret=os.environ["ALPHA_SIGNING_SECRET"],
        key_id="alpha_production_v1",
    )
    return att.model_dump(mode="json"), bp.model_dump(mode="json")


def attach_test_plan(queue: TaskTriageQueue, task_id: str) -> None:
    att, bp = plan_for_task(queue, task_id)
    assert queue.attach_plan(task_id, att, bp)


def approve_with_plan(queue: TaskTriageQueue, task_id: str, *args: Any, **kwargs: Any) -> bool:
    task = queue.get_task(task_id)
    if task and task["status"] == "pending_review":
        # Leave malformed-base tests on their original rejection boundary.
        base = task["envelope"].get("base_commit")
        if "base_commit" in task["envelope"] and not re.fullmatch(
            r"[a-fA-F0-9]{40}", str(base or "")
        ):
            raise ValueError(
                "Task base_commit must be a fully resolved 40-character hexadecimal SHA"
            )
        attach_test_plan(queue, task_id)
    return queue.approve_task(task_id, *args, **kwargs)
