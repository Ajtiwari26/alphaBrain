import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import AttemptRecord, ProjectRecord, TaskRecord, WorkerRecord
from alpha_protocol.task import AgentType, RiskClass, TaskStatus


@pytest.mark.asyncio
async def test_checkpoint_adversarial(setup_db, api_headers):
    session_factory = get_session_factory()
    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_test_123", name="Default Project", status="active", repo_path="/tmp/repo"
        )
        session.add(proj)
        worker = WorkerRecord(id="wrk_test1", hostname="test-worker")
        session.add(worker)
        task_id = "tsk_chk_1"
        task = TaskRecord(
            id=task_id,
            project_id="prj_test_123",
            objective="Test Checkpoint",
            status=TaskStatus.LEASED.value,
            preferred_agent=AgentType.ANTIGRAVITY.value,
            risk_class=RiskClass.LOW.value,
            max_attempts=3,
            details_json={},
            repo="alpha/test",
            lease_token="lse_valid_123",
            worker_id="wrk_test1",
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        session.add(task)

        attempt = AttemptRecord(
            id="att_1", task_id=task_id, agent=AgentType.ANTIGRAVITY.value, model="test-model"
        )
        session.add(attempt)
        await session.commit()

    headers = api_headers

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Valid Append
        chk_payload = {
            "checkpoint": {
                "checkpoint_id": "chk_1",
                "task_id": task_id,
                "attempt_id": "att_1",
                "worker_id": "wrk_test1",
                "attempt_number": 1,
                "sequence": 1,
                "project_id": "prj_test_123",
                "repo_reference": "alpha/test",
                "base_commit": "abc1234",
                "worktree_path": "/tmp/wt1",
                "worktree_head": "def5678",
                "conversation_id": "conv_1",
                "execution_stage": "running",
                "lease_token_hash": hashlib.sha256(b"lse_valid_123").hexdigest(),
                "side_effect_state": "none",
                "scrubbed_payload": {"state": "init"},
                "payload_digest": "dig_1",
                "idempotency_key": "idem_1",
                "created_at": datetime.now(UTC).isoformat(),
            },
            "raw_lease_token": "lse_valid_123",
        }

        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload, headers=headers
        )
        assert resp.status_code == 200, resp.text

        # 2. Duplicate Idempotency Key + Same Digest (should 200)
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload, headers=headers
        )
        assert resp.status_code == 200, resp.text

        # 3. Duplicate Key + Different Digest (Conflict)
        chk_payload_conflict = json.loads(json.dumps(chk_payload))
        chk_payload_conflict["checkpoint"]["payload_digest"] = "dig_2"
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload_conflict, headers=headers
        )
        assert resp.status_code == 409

        # 4. Out-of-Order Sequence
        chk_payload_seq = json.loads(json.dumps(chk_payload))
        chk_payload_seq["checkpoint"]["idempotency_key"] = "idem_2"
        chk_payload_seq["checkpoint"]["sequence"] = 1  # Already exists
        chk_payload_seq["checkpoint"]["checkpoint_id"] = "chk_2"
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload_seq, headers=headers
        )
        assert resp.status_code == 409

        chk_payload_seq["checkpoint"]["sequence"] = 3  # skipped 2
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload_seq, headers=headers
        )
        assert resp.status_code == 409

        # 5. Stale Token
        chk_payload_stale = json.loads(json.dumps(chk_payload))
        chk_payload_stale["raw_lease_token"] = "lse_stale"
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload_stale, headers=headers
        )
        assert resp.status_code == 403

        # 6. Stolen Worker
        chk_payload_stolen = json.loads(json.dumps(chk_payload))
        chk_payload_stolen["checkpoint"]["worker_id"] = "wrk_stolen"
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload_stolen, headers=headers
        )
        assert resp.status_code == 403

        # 7. Unsafe Side-Effects (Resume Decision)
        chk_payload_unsafe = json.loads(json.dumps(chk_payload))
        chk_payload_unsafe["checkpoint"]["checkpoint_id"] = "chk_unsafe"
        chk_payload_unsafe["checkpoint"]["idempotency_key"] = "idem_unsafe"
        chk_payload_unsafe["checkpoint"]["sequence"] = 2
        chk_payload_unsafe["checkpoint"]["side_effect_state"] = "unknown"
        resp = await client.post(
            f"/api/tasks/{task_id}/checkpoints", json=chk_payload_unsafe, headers=headers
        )
        assert resp.status_code == 200

        resume_payload = {
            "worker_id": "wrk_test1",
            "attempt_id": "att_1",
            "project_id": "prj_test_123",
            "repo_reference": "alpha/test",
            "base_commit": "abc1234",
            "worktree_path": "/tmp/wt1",
            "conversation_id": "conv_1",
            "latest_checkpoint_digest": "dig_1",
        }

        resp = await client.post(
            f"/api/tasks/{task_id}/resume-decision", json=resume_payload, headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["safe_to_resume"] is False
        assert "Unsafe side-effect state" in data["reason"]
