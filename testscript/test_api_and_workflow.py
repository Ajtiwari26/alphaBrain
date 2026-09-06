"""
testscript/test_api_and_workflow.py
Integration tests for FastAPI REST endpoints and SDLC workflow runner.
"""

import base64
import hashlib
import hmac
import subprocess
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.security import create_worker_identity_token
from alpha_core.workflow.sdlc_workflow import SDLCWorkflowRunner
from alpha_protocol import (
    AgentType,
    GateEvidence,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    WorkerHealthReport,
    WorkerRegistration,
)


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "device_attached" not in data


@pytest.mark.asyncio
async def test_task_submission_and_details_api(tmp_path, monkeypatch, api_headers):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        envelope = TaskEnvelope(
            task_id="tsk_api_test_01",
            project_id="prj_api",
            repo=str(repo_path),
            objective="Test FastAPI task endpoints",
            allowed_paths=["."],
            preferred_agent=AgentType.ANTIGRAVITY,
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

        # 1. Submit task with JSON-serializable dump
        sub_resp = await ac.post(
            "/api/tasks",
            json=envelope.model_dump(mode="json"),
            headers=api_headers,
        )
        assert sub_resp.status_code == 200
        assert sub_resp.json()["status"] == "queued"

        # 2. Get task details
        get_resp = await ac.get(f"/api/tasks/{envelope.task_id}", headers=api_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["task_id"] == envelope.task_id
        assert get_resp.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_project_registration_is_remote_safe_and_repo_binding_is_immutable(
    tmp_path, monkeypatch, api_headers
):
    """Control plane checks path policy, while Mac worker owns filesystem checks."""
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    repo_reference = allowed_root / "not-mounted-on-control-plane"
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))

    project = {
        "project_id": "prj_remote_binding",
        "name": "Remote-safe project",
        "repo_path": str(repo_reference),
    }
    envelope = TaskEnvelope(
        task_id="tsk_remote_binding_01",
        project_id=project["project_id"],
        repo=project["repo_path"],
        objective="Execute only on outbound Mac worker",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        registered = await ac.post("/api/projects", json=project, headers=api_headers)
        repeated = await ac.post("/api/projects", json=project, headers=api_headers)
        submitted = await ac.post(
            "/api/tasks",
            json=envelope.model_dump(mode="json"),
            headers=api_headers,
        )
        rebound = await ac.post(
            "/api/projects",
            json={**project, "repo_path": str(allowed_root / "different")},
            headers=api_headers,
        )

    assert not repo_reference.exists()
    assert registered.status_code == 200
    assert registered.json()["status"] == "registered"
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "existing"
    assert submitted.status_code == 200
    assert rebound.status_code == 409


@pytest.mark.asyncio
async def test_project_registration_rejects_repo_reference_outside_allowed_roots(
    tmp_path, monkeypatch, api_headers
):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/projects",
            json={
                "project_id": "prj_outside_root",
                "name": "Rejected project",
                "repo_path": str(tmp_path / "outside"),
            },
            headers=api_headers,
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Repository reference is outside allowed roots"


@pytest.mark.asyncio
async def test_staging_rejects_task_until_project_is_registered(tmp_path, monkeypatch, api_headers):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    repo_reference = allowed_root / "mac-only-repo"
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    monkeypatch.setattr(settings, "ENV", "staging")
    envelope = TaskEnvelope(
        task_id="tsk_staging_requires_project",
        project_id="prj_staging_requires_project",
        repo=str(repo_reference),
        objective="Reject implicit remote project creation",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        rejected = await ac.post(
            "/api/tasks",
            json=envelope.model_dump(mode="json"),
            headers=api_headers,
        )
        registered = await ac.post(
            "/api/projects",
            json={
                "project_id": envelope.project_id,
                "name": "Registered staging project",
                "repo_path": envelope.repo,
            },
            headers=api_headers,
        )
        accepted = await ac.post(
            "/api/tasks",
            json=envelope.model_dump(mode="json"),
            headers=api_headers,
        )

    assert rejected.status_code == 404
    assert rejected.json()["detail"] == (
        "Project must be registered before submitting remote tasks"
    )
    assert registered.status_code == 200
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_task_repo_must_match_registered_project_binding(tmp_path, monkeypatch, api_headers):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    project = {
        "project_id": "prj_task_repo_binding",
        "name": "Bound project",
        "repo_path": str(allowed_root / "expected"),
    }
    envelope = TaskEnvelope(
        task_id="tsk_wrong_repo_binding",
        project_id=project["project_id"],
        repo=str(allowed_root / "wrong"),
        objective="Never execute against mismatched repository",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        registered = await ac.post("/api/projects", json=project, headers=api_headers)
        rejected = await ac.post(
            "/api/tasks",
            json=envelope.model_dump(mode="json"),
            headers=api_headers,
        )

    assert registered.status_code == 200
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == (
        "Task repository does not match registered project binding"
    )


@pytest.mark.asyncio
async def test_approval_required_task_needs_founder_decision(tmp_path, monkeypatch, api_headers):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    envelope = TaskEnvelope(
        task_id="tsk_api_approval_01",
        project_id="prj_api_approval",
        repo=str(repo_path),
        objective="Do not start before founder approval",
        allowed_paths=["."],
        preferred_agent=AgentType.ANTIGRAVITY,
        requires_approval=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        submitted = await ac.post(
            "/api/tasks", json=envelope.model_dump(mode="json"), headers=api_headers
        )
        before = await ac.get(f"/api/tasks/{envelope.task_id}", headers=api_headers)
        approved = await ac.post(
            f"/api/tasks/{envelope.task_id}/approval",
            json={"approved": True, "reason": "Go"},
            headers=api_headers,
        )
        after = await ac.get(f"/api/tasks/{envelope.task_id}", headers=api_headers)

    assert submitted.json()["status"] == "waiting_approval"
    assert before.json()["status"] == "waiting_approval"
    assert approved.json()["status"] == "queued"
    assert after.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_project_progress_snapshot_reports_safe_task_state(
    tmp_path, monkeypatch, api_headers
):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    envelope = TaskEnvelope(
        task_id="tsk_api_progress_01",
        project_id="prj_api_progress",
        repo=str(repo_path),
        objective="Show approval in progress report",
        allowed_paths=["."],
        requires_approval=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        submitted = await ac.post(
            "/api/tasks", json=envelope.model_dump(mode="json"), headers=api_headers
        )
        report = await ac.get(f"/api/projects/{envelope.project_id}/progress", headers=api_headers)

    assert submitted.status_code == 200
    assert report.status_code == 200
    payload = report.json()
    assert payload["waiting_approval_tasks"] == 1
    assert payload["next_owner_action"] == "founder_approval_required"
    assert payload["recent_events"][0]["event_type"] == "task_queued"


@pytest.mark.asyncio
async def test_founder_can_queue_clean_self_development_task_without_starting_execution(
    tmp_path, monkeypatch, api_headers
):
    repo_path = tmp_path / "alpha-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    (repo_path / "README.md").write_text("self-development proof\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Alpha Test",
            "-c",
            "user.email=alpha@example.test",
            "commit",
            "-m",
            "initial",
        ],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    payload = {
        "task_id": "tsk_self_api_001",
        "project_id": "prj_self_api",
        "source_repo": str(repo_path),
        "allowed_paths": ["alpha_core", "testscript"],
        "objective": "Add one bounded self-development proof",
        "acceptance_plan": {
            "required_gates": ["independent_review", "code_review_graph", "lint", "unit_test"],
            "commands": [
                {"gate_type": "lint", "executable": "ruff", "args": ["check", "alpha_core"]},
                {
                    "gate_type": "unit_test",
                    "executable": "pytest",
                    "args": ["testscript/test_self_development_admission.py"],
                },
            ],
            "require_independent_review": True,
        },
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/self-development/tasks", json=payload, headers=api_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == TaskStatus.WAITING_APPROVAL.value
    assert body["execution_started"] is False
    assert body["next_owner_action"] == "founder_approval_required"


@pytest.mark.asyncio
async def test_signed_worker_can_register_report_health_and_be_read_by_founder(
    api_headers, worker_headers
):
    worker_id = "mac-worker-api-test"
    identity = create_worker_identity_token(worker_id)
    worker_auth = {**worker_headers, "X-Alpha-Worker-Identity": identity}
    registration = WorkerRegistration(worker_id=worker_id, hostname="Test-Mac")
    health = WorkerHealthReport(
        worker_id=worker_id,
        battery_percent=94,
        ac_power=True,
        thermal_pressure="nominal",
        active_task_count=1,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        registered = await ac.post(
            "/api/workers/register",
            json=registration.model_dump(mode="json"),
            headers=worker_auth,
        )
        reported = await ac.post(
            f"/api/workers/{worker_id}/health",
            json=health.model_dump(mode="json"),
            headers=worker_auth,
        )
        status = await ac.get(f"/api/workers/{worker_id}", headers=api_headers)

    assert registered.json()["status"] == "registered"
    assert reported.json()["worker_status"] == "online"
    assert status.json()["latest_health"]["battery_percent"] == 94
    assert status.json()["latest_health"]["active_task_count"] == 1


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending", strict=True, raises=AssertionError)
async def test_worker_control_plane_lease_heartbeat_result_vertical_slice(
    tmp_path, monkeypatch, api_headers, worker_headers
):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    worker_id = "mac-worker-e2e"
    worker_auth = {
        **worker_headers,
        "X-Alpha-Worker-Identity": create_worker_identity_token(worker_id),
    }
    envelope = TaskEnvelope(
        task_id="tsk-worker-e2e",
        project_id="prj-worker-e2e",
        repo=str(repo_path),
        objective="Exercise worker control plane",
        allowed_paths=["."],
        preferred_agent=AgentType.ANTIGRAVITY,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    result = TaskResult(
        attempt_id="att-worker-e2e",
        task_id=envelope.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        gate_result=GateResult(
            task_id="tsk-worker-e2e",
            attempt_id="att-worker-e2e",
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id="evi-lint-e2e",
                    gate_type=GateType.LINT,
                    passed=True,
                    summary="Lint check passed",
                ),
                GateEvidence(
                    evidence_id="evi-unit-e2e",
                    gate_type=GateType.UNIT_TEST,
                    passed=True,
                    summary="Unit tests passed",
                ),
            ],
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/workers/register",
            json=WorkerRegistration(worker_id=worker_id, hostname="test").model_dump(mode="json"),
            headers=worker_auth,
        )
        queued = await ac.post(
            "/api/tasks", json=envelope.model_dump(mode="json"), headers=api_headers
        )
        leased = await ac.post(
            "/api/tasks/lease",
            json={"worker_id": worker_id, "preferred_agent": AgentType.ANTIGRAVITY.value},
            headers=worker_auth,
        )
        token = leased.json()["lease_token"]
        heartbeat = await ac.post(
            f"/api/tasks/{envelope.task_id}/heartbeat",
            json={"lease_token": token},
            headers=worker_auth,
        )
        completed = await ac.post(
            f"/api/tasks/{envelope.task_id}/result",
            json={"lease_token": token, "result": result.model_dump(mode="json")},
            headers=worker_auth,
        )
    assert queued.json()["status"] == "queued"
    assert leased.json()["status"] == "leased"
    assert heartbeat.json()["status"] == "heartbeat_recorded"
    print(completed.json())
    assert completed.json()["status"] == "result_recorded"


@pytest.mark.asyncio
async def test_founder_cancellation_reaches_authenticated_active_worker(
    tmp_path, monkeypatch, api_headers, worker_headers
):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    worker_id = "mac-worker-cancel"
    worker_auth = {
        **worker_headers,
        "X-Alpha-Worker-Identity": create_worker_identity_token(worker_id),
    }
    envelope = TaskEnvelope(
        task_id="tsk-worker-cancel",
        project_id="prj-worker-cancel",
        repo=str(repo_path),
        objective="Prove active cancellation delivery",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/workers/register",
            json=WorkerRegistration(worker_id=worker_id, hostname="test").model_dump(mode="json"),
            headers=worker_auth,
        )
        await ac.post("/api/tasks", json=envelope.model_dump(mode="json"), headers=api_headers)
        leased = await ac.post(
            "/api/tasks/lease",
            json={"worker_id": worker_id},
            headers=worker_auth,
        )
        lease_token = leased.json()["lease_token"]
        cancelled = await ac.post(
            f"/api/tasks/{envelope.task_id}/cancel",
            json={"reason": "Founder stopped test execution"},
            headers=api_headers,
        )
        signal = await ac.post(
            f"/api/tasks/{envelope.task_id}/heartbeat",
            json={"lease_token": lease_token},
            headers=worker_auth,
        )

    assert cancelled.status_code == 200
    assert cancelled.json()["worker_signal_pending"] is True
    assert signal.status_code == 200
    assert signal.json()["status"] == "cancel_requested"


@pytest.mark.asyncio
async def test_plivo_incoming_xml():
    nonce = f"nonce-{uuid.uuid4().hex}"
    uri = "http://test/api/voice/plivo/incoming"
    signature = base64.b64encode(
        hmac.new(
            settings.PLIVO_AUTH_TOKEN.encode("utf-8"),
            f"{uri}{nonce}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/voice/plivo/incoming",
            headers={
                "X-Plivo-Signature-V3": signature,
                "X-Plivo-Signature-V3-Nonce": nonce,
            },
        )
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Stream" in response.text
    assert 'bidirectional="true"' in response.text


@pytest.mark.asyncio
async def test_sdlc_workflow_runner():
    runner = SDLCWorkflowRunner(
        project_id="prj_sdlc_test",
        repo_path="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
    )
    result = await runner.run("Client wants a dark mode dashboard with real-time graphs.")
    assert result["project_id"] == "prj_sdlc_test"
    assert result["final_state"] == "DEPLOYED"
    assert "spec" in result
    assert "call_job" in result


@pytest.mark.asyncio
async def test_result_submission_rejects_task_id_mismatch(
    tmp_path, monkeypatch, api_headers, worker_headers
):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    worker_id = "mac-worker-e2e"
    worker_auth = {
        **worker_headers,
        "X-Alpha-Worker-Identity": create_worker_identity_token(worker_id),
    }
    envelope = TaskEnvelope(
        task_id="tsk-match-test",
        project_id="prj-worker-e2e",
        repo=str(repo_path),
        objective="Test mismatch",
        allowed_paths=["."],
        preferred_agent=AgentType.ANTIGRAVITY,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    result = TaskResult(
        attempt_id="att-match-test",
        task_id="tsk-DIFFERENT",
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        gate_result=GateResult(
            task_id="tsk-DIFFERENT",
            attempt_id="att-match-test",
            all_passed=True,
            evidence_items=[],
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/workers/register",
            json=WorkerRegistration(worker_id=worker_id, hostname="test").model_dump(mode="json"),
            headers=worker_auth,
        )
        await ac.post("/api/tasks", json=envelope.model_dump(mode="json"), headers=api_headers)
        leased = await ac.post(
            "/api/tasks/lease",
            json={"worker_id": worker_id, "preferred_agent": AgentType.ANTIGRAVITY.value},
            headers=worker_auth,
        )
        token = leased.json()["lease_token"]

        response = await ac.post(
            f"/api/tasks/{envelope.task_id}/result",
            json={"lease_token": token, "result": result.model_dump(mode="json")},
            headers=worker_auth,
        )

    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()
