import base64
import hashlib
import hmac
import subprocess
import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.security import (
    create_meeting_invite,
    create_worker_identity_token,
    verify_meeting_invite,
)
from alpha_meet.eva_live_agent import eva_room_manager
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateCommand,
    GateType,
    TaskEnvelope,
)
from alpha_worker.adapters.base import BaseAgentAdapter
from alpha_worker.worktree import WorktreeManager


class GateOnlyAdapter(BaseAgentAdapter):
    def __init__(self):
        super().__init__(AgentType.ANTIGRAVITY)

    def check_readiness(self):
        return True, "ready"

    async def execute(self, task, worktree_path, base_commit):
        raise NotImplementedError


def make_task(**overrides):
    data = {
        "task_id": "tsk_security_01",
        "project_id": "prj_security",
        "repo": "/Users/ajaytiwari/Desktop/Projects/example",
        "objective": "Run security boundary test",
        "allowed_paths": ["src"],
    }
    data.update(overrides)
    return TaskEnvelope(**data, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending", strict=True, raises=AssertionError)
async def test_private_and_worker_routes_require_separate_tokens(api_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        task_response = await client.post(
            "/api/tasks",
            json=make_task().model_dump(mode="json"),
        )
        lease_with_api_token = await client.post(
            "/api/tasks/lease",
            json={"worker_id": "worker-security"},
            headers=api_headers,
        )

    assert task_response.status_code == 401
    assert lease_with_api_token.status_code == 401


@pytest.mark.asyncio
async def test_worker_cannot_claim_another_worker_identity(worker_headers):
    worker_identity = create_worker_identity_token("mac-worker-a")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.post(
            "/api/tasks/lease",
            json={"worker_id": "mac-worker-a"},
            headers={**worker_headers, "X-Alpha-Worker-Identity": worker_identity},
        )
        denied = await client.post(
            "/api/tasks/lease",
            json={"worker_id": "mac-worker-b"},
            headers={**worker_headers, "X-Alpha-Worker-Identity": worker_identity},
        )

    assert allowed.status_code == 200
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_meeting_admin_grant_is_server_controlled(api_headers, monkeypatch):
    async def fake_ensure_room(room_name, **_kwargs):
        return {"identity": "eva-cto", "room_name": room_name, "state": "ready"}

    monkeypatch.setattr(eva_room_manager, "ensure_room", fake_ensure_room)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/meet/token",
            headers=api_headers,
            json={
                "room_name": "security-room",
                "identity": "Security Tester",
                "is_admin": True,
            },
        )
        invite = create_meeting_invite("security-room", "Security Client", role="client")
        client_response = await client.post(
            "/api/meet/token",
            json={"invite_token": invite},
        )

    assert response.status_code == 200
    founder_claims = jwt.decode(
        response.json()["token"],
        settings.LIVEKIT_API_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert founder_claims["video"]["roomAdmin"] is True
    assert client_response.status_code == 200
    client_claims = jwt.decode(
        client_response.json()["token"],
        settings.LIVEKIT_API_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert client_claims["video"]["roomAdmin"] is False
    assert client_claims["video"]["canUpdateOwnMetadata"] is False


def test_meeting_invite_rejects_tampering_and_expiry(monkeypatch):
    monkeypatch.setattr("alpha_core.security.time.time", lambda: 1_000)
    invite = create_meeting_invite("security-room", "Client", ttl_seconds=60)
    claims = verify_meeting_invite(invite)
    assert claims is not None
    assert claims["room"] == "security-room"
    assert verify_meeting_invite(f"{invite[:-1]}x") is None

    monkeypatch.setattr("alpha_core.security.time.time", lambda: 1_061)
    assert verify_meeting_invite(invite) is None


@pytest.mark.asyncio
async def test_plivo_signature_replay_is_rejected():
    nonce = f"nonce-{uuid.uuid4().hex}"
    uri = "http://test/api/voice/plivo/incoming"
    signature = base64.b64encode(
        hmac.new(
            settings.PLIVO_AUTH_TOKEN.encode(),
            f"{uri}{nonce}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    headers = {
        "X-Plivo-Signature-V3": signature,
        "X-Plivo-Signature-V3-Nonce": nonce,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        invalid = await client.post(
            "/api/voice/plivo/incoming",
            headers={
                **headers,
                "X-Plivo-Signature-V3": "invalid-signature",
            },
        )
        first = await client.post("/api/voice/plivo/incoming", headers=headers)
        replay = await client.post("/api/voice/plivo/incoming", headers=headers)

    assert invalid.status_code == 401
    assert first.status_code == 200
    assert replay.status_code == 401


def test_raw_shell_commands_and_path_traversal_are_rejected():
    with pytest.raises(ValidationError, match="custom_commands is unsafe"):
        AcceptancePlan(custom_commands=["touch /tmp/unsafe"])

    with pytest.raises(ValidationError, match="allowed_paths"):
        make_task(allowed_paths=["../outside"])

    with pytest.raises(ValidationError, match="task_id"):
        make_task(task_id="../../escape")


def test_required_gate_without_evidence_fails(tmp_path):
    task = make_task(
        acceptance_plan=AcceptancePlan(required_gates=[GateType.UNIT_TEST]),
    )
    result = GateOnlyAdapter().run_acceptance_gates(task, tmp_path, "att_security")

    assert result.all_passed is False
    assert len(result.evidence_items) == 1
    assert result.evidence_items[0].gate_type == GateType.UNIT_TEST
    assert "produced no evidence" in result.evidence_items[0].summary


def test_gate_execution_uses_argument_array_without_shell(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="passed", stderr="")

    monkeypatch.setattr(settings, "ALLOWED_GATE_EXECUTABLES", ("pytest",))
    monkeypatch.setattr("alpha_worker.adapters.base.shutil.which", lambda _: "/usr/bin/pytest")
    monkeypatch.setattr("alpha_worker.adapters.base.subprocess.run", fake_run)

    task = make_task(
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["-q", "testscript/"],
                )
            ],
        )
    )
    result = GateOnlyAdapter().run_acceptance_gates(task, tmp_path, "att_security")

    assert result.all_passed is True
    assert calls[0][0] == ["/usr/bin/pytest", "-q", "testscript/"]
    assert calls[0][1]["shell"] is False


def test_repository_and_changed_path_boundaries(tmp_path, monkeypatch):
    allowed_root = tmp_path / "projects"
    allowed_root.mkdir()
    repository = allowed_root / "repo"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    assert WorktreeManager.validate_repo_path(str(repository)) == repository.resolve()
    with pytest.raises(ValueError, match="outside allowed roots"):
        WorktreeManager.validate_repo_path(str(tmp_path / "outside"))

    violations = WorktreeManager.find_disallowed_changes(
        ["src/allowed.py", "secrets.env"],
        ["src"],
    )
    assert violations == ["secrets.env"]


@pytest.mark.asyncio
async def test_invalid_worker_identity_token_returns_401(worker_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tampered_response = await client.post(
            "/api/tasks/lease",
            json={"worker_id": "mac-worker-tampered"},
            headers={**worker_headers, "X-Alpha-Worker-Identity": "invalid.fake.token"},
        )
        assert tampered_response.status_code == 401
        assert "Invalid worker identity" in tampered_response.json()["detail"]


@pytest.mark.asyncio
async def test_expired_worker_identity_token_returns_401(worker_headers, monkeypatch):
    import alpha_core.security as sec_mod

    monkeypatch.setattr(sec_mod.time, "time", lambda: 1000)
    token = create_worker_identity_token("mac-worker-exp", ttl_seconds=10)

    monkeypatch.setattr(sec_mod.time, "time", lambda: 1020)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        expired_response = await client.post(
            "/api/tasks/lease",
            json={"worker_id": "mac-worker-exp"},
            headers={**worker_headers, "X-Alpha-Worker-Identity": token},
        )
        assert expired_response.status_code == 401
        assert "Invalid worker identity" in expired_response.json()["detail"]
