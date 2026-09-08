import json

import pytest
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app, get_triage_queue, portal_stream_generator
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_core.security import (
    AuthPrincipal,
    PrincipalRole,
    create_scoped_stream_token,
    require_api_principal,
)


def test_project_task_events_table_and_queries(tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)

    seq1 = queue.record_project_event(
        project_id="prj_alpha",
        task_id="tsk_001",
        state="received",
        status="pending_review",
        event_type="task_admitted",
        payload={"title": "Fix login bug"},
    )
    seq2 = queue.record_project_event(
        project_id="prj_alpha",
        task_id="tsk_001",
        state="in_progress",
        status="in_progress",
        event_type="task_leased",
    )
    seq3 = queue.record_project_event(
        project_id="prj_beta",
        task_id="tsk_002",
        state="received",
        status="pending_review",
        event_type="task_admitted",
    )

    assert seq1 == 1
    assert seq2 == 2
    assert seq3 == 3

    # Query all events for prj_alpha
    alpha_events = queue.get_project_events("prj_alpha", after_seq=0)
    assert len(alpha_events) == 2
    assert alpha_events[0]["seq"] == 1
    assert alpha_events[0]["state"] == "received"
    assert alpha_events[1]["seq"] == 2
    assert alpha_events[1]["state"] == "in_progress"

    # Replay after seq1 should only return seq2
    replay_events = queue.get_project_events("prj_alpha", after_seq=1)
    assert len(replay_events) == 1
    assert replay_events[0]["seq"] == 2


@pytest.mark.asyncio
async def test_portal_stream_emits_real_events_with_state(tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)

    queue.record_project_event(
        project_id="prj_live",
        task_id="tsk_live_1",
        state="in_progress",
        status="executing",
        event_type="task_leased",
    )

    generator = portal_stream_generator(
        project_id="prj_live",
        last_event_id=None,
        max_duration_seconds=3,
        poll_interval_seconds=0.1,
        queue=queue,
    )

    messages = []
    async for chunk in generator:
        messages.append(chunk)
        if "task_update" in chunk:
            break

    assert len(messages) >= 1
    msg = messages[-1]
    assert "id: 1\n" in msg
    assert "event: task_update\n" in msg

    # Parse JSON payload
    data_line = next(line for line in msg.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.replace("data: ", ""))
    assert payload["task_id"] == "tsk_live_1"
    assert payload["state"] == "in_progress"
    assert payload["status"] == "executing"
    assert payload["live"] is True


@pytest.mark.asyncio
async def test_portal_stream_durable_replay(tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)

    queue.record_project_event("prj_replay", "tsk_1", "received", "pending_review", "task_admitted")
    queue.record_project_event("prj_replay", "tsk_1", "in_progress", "in_progress", "task_leased")
    queue.record_project_event("prj_replay", "tsk_1", "review", "completed", "task_completed")

    # Reconnect with last_event_id = "2"
    generator = portal_stream_generator(
        project_id="prj_replay",
        last_event_id="2",
        max_duration_seconds=2,
        poll_interval_seconds=0.1,
        queue=queue,
    )

    messages = []
    async for chunk in generator:
        messages.append(chunk)
        if "task_update" in chunk:
            break

    # Should immediately stream event 3
    assert len(messages) >= 1
    assert "id: 3\n" in messages[-1]
    data_line = next(line for line in messages[-1].splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.replace("data: ", ""))
    assert payload["state"] == "review"
    assert payload["status"] == "completed"


@pytest.mark.asyncio
async def test_stream_endpoint_durable_replay_e2e(tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)

    queue.record_project_event("prj_e2e", "tsk_e2e_1", "received", "pending", "task_admitted")
    queue.record_project_event("prj_e2e", "tsk_e2e_1", "in_progress", "executing", "task_leased")

    app.dependency_overrides[TaskTriageQueue] = lambda: queue
    app.dependency_overrides[get_triage_queue] = lambda: queue
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="test_admin", role=PrincipalRole.ADMIN
    )

    token = create_scoped_stream_token("portal-stream:prj_e2e", ttl_seconds=3600)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            async with ac.stream(
                "GET",
                f"/api/portal/projects/prj_e2e/stream?token={token}&max_iterations=1",
                headers={"Last-Event-ID": "1"},
            ) as response:
                assert response.status_code == 200
                lines = []
                async for line in response.aiter_lines():
                    if line.strip():
                        lines.append(line)
                    if "event: task_update" in line:
                        break

                # The replayed event must be seq 2
                assert "id: 2" in lines
                assert "event: task_update" in lines
    finally:
        app.dependency_overrides.clear()
