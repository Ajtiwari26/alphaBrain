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
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.db.connection import init_db
from alpha_core.workflow.sdlc_workflow import SDLCWorkflowRunner
from alpha_protocol import AgentType, TaskEnvelope


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_db()


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
    assert "bidirectional=\"true\"" in response.text


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
