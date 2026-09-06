"""
testscript/test_project_event_log_api.py
Strict TDD Test Suite for P4.2: Durable Project Event Log API
Endpoint: GET /api/projects/{project_id}/events

Contract & Test Matrix:
1. Founder receives ordered project-only events (descending timestamp, then id).
2. Category filter returns only matching classification.
3. Keyset cursor produces stable non-overlapping pages (no offset pagination).
4. Same timestamp ordering uses id as deterministic tie-breaker.
5. Malformed cursor returns 422.
6. Founder sees sanitized actor/details (actual actor identity + sanitized details, no raw secrets).
7. Client sees actor='system' and redacted details (scrubbed internal telemetry, paths, tokens).
8. Cross-project principal receives 403 with no event leakage.
9. Unknown project for authorized principal returns 404.
10. Unknown event type remains visible as category 'work'.
11. Raw secret/token/path-like values inserted into audit details never appear in response.
12. Limit boundaries and query validation (default 25, min 1, max 100).
13. Empty project event log returns clean empty response.
14. Unauthenticated or invalid token requests return 401.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import AuditEventRecord, ProjectRecord
from alpha_core.security import PrincipalRole, create_scoped_principal_token


def encode_cursor(timestamp: datetime, event_id: str) -> str:
    """Encode keyset cursor as base64-encoded JSON payload."""
    payload = {"timestamp": timestamp.isoformat(), "id": event_id}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def founder_headers(api_headers):
    """Bearer token for founder/admin principal with full system access."""
    return api_headers


@pytest.fixture
def client_headers_factory():
    """Factory to produce scoped client authorization headers for specific projects."""

    def _make(project_ids: list[str], subject: str = "client_user_01"):
        token = create_scoped_principal_token(
            subject=subject,
            role=PrincipalRole.CLIENT,
            project_ids=project_ids,
        )
        return {"Authorization": f"Bearer {token}"}

    return _make


# ---------------------------------------------------------------------------
# 1. Founder receives ordered project-only events (descending timestamp, then id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_founder_receives_ordered_project_only_events(setup_db, founder_headers):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        # Create Project A and Project B
        proj_a = ProjectRecord(
            id="prj_alpha", name="Project Alpha", repo_path="/repos/alpha", status="active"
        )
        proj_b = ProjectRecord(
            id="prj_beta", name="Project Beta", repo_path="/repos/beta", status="active"
        )
        session.add_all([proj_a, proj_b])

        # Project A events (staggered timestamps)
        evt_a1 = AuditEventRecord(
            id="evt_a1",
            project_id="prj_alpha",
            event_type="project_created",
            actor="founder_ajay",
            details_json={"action": "created"},
            timestamp=t0,
        )
        evt_a2 = AuditEventRecord(
            id="evt_a2",
            project_id="prj_alpha",
            event_type="task_queued",
            task_id="tsk_01",
            actor="founder_ajay",
            details_json={"task_id": "tsk_01"},
            timestamp=t0 + timedelta(seconds=10),
        )
        evt_a3 = AuditEventRecord(
            id="evt_a3",
            project_id="prj_alpha",
            event_type="task_leased",
            task_id="tsk_01",
            actor="wrk_01",
            details_json={"worker": "wrk_01"},
            timestamp=t0 + timedelta(seconds=20),
        )

        # Project B event
        evt_b1 = AuditEventRecord(
            id="evt_b1",
            project_id="prj_beta",
            event_type="task_queued",
            task_id="tsk_b01",
            actor="founder_ajay",
            details_json={"task_id": "tsk_b01"},
            timestamp=t0 + timedelta(seconds=30),
        )
        session.add_all([evt_a1, evt_a2, evt_a3, evt_b1])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/projects/prj_alpha/events", headers=founder_headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "events" in data
    assert data["returned_count"] == 3
    assert len(data["events"]) == 3

    event_ids = [e["id"] for e in data["events"]]
    # Must be strictly descending by timestamp: evt_a3, evt_a2, evt_a1
    assert event_ids == ["evt_a3", "evt_a2", "evt_a1"]

    # Must not contain Project B event
    assert "evt_b1" not in event_ids


# ---------------------------------------------------------------------------
# 2. Category filter returns only matching classification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_category_filter_returns_only_matching_classification(setup_db, founder_headers):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_cat_test", name="Category Test Proj", repo_path="/repos/cat", status="active"
        )
        session.add(proj)

        events = [
            AuditEventRecord(
                id="evt_proj_1",
                project_id="prj_cat_test",
                event_type="spec_submitted",
                actor="founder_ajay",
                details_json={"spec_version": 1},
                timestamp=t0 + timedelta(seconds=1),
            ),
            AuditEventRecord(
                id="evt_task_1",
                project_id="prj_cat_test",
                event_type="task_leased",
                task_id="tsk_101",
                actor="wrk_01",
                details_json={"lease_token": "lse_1"},
                timestamp=t0 + timedelta(seconds=2),
            ),
            AuditEventRecord(
                id="evt_work_1",
                project_id="prj_cat_test",
                event_type="task_heartbeat",
                task_id="tsk_101",
                actor="wrk_01",
                details_json={"step": 3},
                timestamp=t0 + timedelta(seconds=3),
            ),
            AuditEventRecord(
                id="evt_qa_1",
                project_id="prj_cat_test",
                event_type="gate_evidence_submitted",
                task_id="tsk_101",
                actor="wrk_01",
                details_json={"gate": "lint", "passed": True},
                timestamp=t0 + timedelta(seconds=4),
            ),
            AuditEventRecord(
                id="evt_prev_1",
                project_id="prj_cat_test",
                event_type="preview_ready",
                task_id="tsk_101",
                actor="system",
                details_json={"url": "https://preview.local"},
                timestamp=t0 + timedelta(seconds=5),
            ),
            AuditEventRecord(
                id="evt_inc_1",
                project_id="prj_cat_test",
                event_type="watchdog_stalled",
                task_id="tsk_101",
                actor="system",
                details_json={"reason": "stalled heartbeat"},
                timestamp=t0 + timedelta(seconds=6),
            ),
        ]
        session.add_all(events)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test each category
        categories_to_expected = {
            "project": ["evt_proj_1"],
            "task": ["evt_task_1"],
            "work": ["evt_work_1"],
            "qa": ["evt_qa_1"],
            "preview": ["evt_prev_1"],
            "incident": ["evt_inc_1"],
        }

        for category, expected_ids in categories_to_expected.items():
            resp = await client.get(
                f"/api/projects/prj_cat_test/events?category={category}",
                headers=founder_headers,
            )
            assert resp.status_code == 200, f"Failed for category {category}: {resp.text}"
            data = resp.json()
            returned_ids = [e["id"] for e in data["events"]]
            assert returned_ids == expected_ids, f"Mismatch for category {category}"
            assert all(e["category"] == category for e in data["events"])

        # Test invalid category
        resp_invalid = await client.get(
            "/api/projects/prj_cat_test/events?category=invalid_category_xyz",
            headers=founder_headers,
        )
        assert resp_invalid.status_code == 422


# ---------------------------------------------------------------------------
# 3. Keyset cursor produces stable non-overlapping pages (no offset pagination)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_keyset_cursor_produces_stable_non_overlapping_pages(setup_db, founder_headers):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 14, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_page_test",
            name="Pagination Test Proj",
            repo_path="/repos/page",
            status="active",
        )
        session.add(proj)

        events = [
            AuditEventRecord(
                id=f"evt_p_{i}",
                project_id="prj_page_test",
                event_type="task_queued",
                task_id=f"tsk_{i}",
                actor="founder_ajay",
                details_json={"index": i},
                timestamp=t0 + timedelta(seconds=i * 10),
            )
            for i in range(1, 6)
        ]  # evt_p_1 (t0+10s) to evt_p_5 (t0+50s)
        session.add_all(events)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Page 1 (limit=2)
        resp1 = await client.get(
            "/api/projects/prj_page_test/events?limit=2", headers=founder_headers
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert len(data1["events"]) == 2
        assert [e["id"] for e in data1["events"]] == ["evt_p_5", "evt_p_4"]
        cursor1 = data1["next_cursor"]
        assert cursor1 is not None

        # Page 2 (limit=2 with cursor)
        resp2 = await client.get(
            f"/api/projects/prj_page_test/events?limit=2&cursor={cursor1}", headers=founder_headers
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["events"]) == 2
        assert [e["id"] for e in data2["events"]] == ["evt_p_3", "evt_p_2"]
        cursor2 = data2["next_cursor"]
        assert cursor2 is not None

        # Page 3 (limit=2 with cursor)
        resp3 = await client.get(
            f"/api/projects/prj_page_test/events?limit=2&cursor={cursor2}", headers=founder_headers
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert len(data3["events"]) == 1
        assert [e["id"] for e in data3["events"]] == ["evt_p_1"]
        cursor3 = data3["next_cursor"]
        assert cursor3 is None  # End of stream

        # Verify all 5 items are distinct and non-overlapping across pages
        all_ids = (
            [e["id"] for e in data1["events"]]
            + [e["id"] for e in data2["events"]]
            + [e["id"] for e in data3["events"]]
        )
        assert all_ids == ["evt_p_5", "evt_p_4", "evt_p_3", "evt_p_2", "evt_p_1"]
        assert len(set(all_ids)) == 5


# ---------------------------------------------------------------------------
# 4. Same timestamp ordering uses id as deterministic tie-breaker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_same_timestamp_ordering_uses_id_as_deterministic_tie_breaker(
    setup_db, founder_headers
):
    session_factory = get_session_factory()
    t_same = datetime(2026, 9, 2, 16, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_tie_test", name="Tie Breaker Proj", repo_path="/repos/tie", status="active"
        )
        session.add(proj)

        # 3 events with EXACT SAME timestamp
        events = [
            AuditEventRecord(
                id="evt_tie_01",
                project_id="prj_tie_test",
                event_type="task_queued",
                task_id="tsk_01",
                actor="system",
                details_json={},
                timestamp=t_same,
            ),
            AuditEventRecord(
                id="evt_tie_02",
                project_id="prj_tie_test",
                event_type="task_queued",
                task_id="tsk_02",
                actor="system",
                details_json={},
                timestamp=t_same,
            ),
            AuditEventRecord(
                id="evt_tie_03",
                project_id="prj_tie_test",
                event_type="task_queued",
                task_id="tsk_03",
                actor="system",
                details_json={},
                timestamp=t_same,
            ),
        ]
        session.add_all(events)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Fetch page 1 (limit 2)
        resp1 = await client.get(
            "/api/projects/prj_tie_test/events?limit=2", headers=founder_headers
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        # Descending tie-breaker by ID: evt_tie_03, then evt_tie_02
        assert [e["id"] for e in data1["events"]] == ["evt_tie_03", "evt_tie_02"]
        cursor1 = data1["next_cursor"]
        assert cursor1 is not None

        # Fetch page 2 (limit 2)
        resp2 = await client.get(
            f"/api/projects/prj_tie_test/events?limit=2&cursor={cursor1}", headers=founder_headers
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert [e["id"] for e in data2["events"]] == ["evt_tie_01"]
        assert data2["next_cursor"] is None


# ---------------------------------------------------------------------------
# 5. Malformed cursor returns 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_malformed_cursor_returns_422(setup_db, founder_headers):
    session_factory = get_session_factory()
    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_cursor_test", name="Cursor Proj", repo_path="/repos/cursor", status="active"
        )
        session.add(proj)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Non-base64 garbage
        resp = await client.get(
            "/api/projects/prj_cursor_test/events?cursor=not-valid-base64!@#$",
            headers=founder_headers,
        )
        assert resp.status_code == 422

        # 2. Base64 encoded non-JSON string
        bad_json_b64 = base64.b64encode(b"plain text string").decode("utf-8")
        resp = await client.get(
            f"/api/projects/prj_cursor_test/events?cursor={bad_json_b64}",
            headers=founder_headers,
        )
        assert resp.status_code == 422

        # 3. Base64 JSON missing 'id'
        missing_id_b64 = base64.b64encode(
            json.dumps({"timestamp": "2026-09-02T20:00:00Z"}).encode("utf-8")
        ).decode("utf-8")
        resp = await client.get(
            f"/api/projects/prj_cursor_test/events?cursor={missing_id_b64}",
            headers=founder_headers,
        )
        assert resp.status_code == 422

        # 4. Base64 JSON missing 'timestamp'
        missing_ts_b64 = base64.b64encode(json.dumps({"id": "evt_123"}).encode("utf-8")).decode(
            "utf-8"
        )
        resp = await client.get(
            f"/api/projects/prj_cursor_test/events?cursor={missing_ts_b64}",
            headers=founder_headers,
        )
        assert resp.status_code == 422

        # 5. Base64 JSON with invalid timestamp format
        bad_ts_b64 = base64.b64encode(
            json.dumps({"timestamp": "not-a-datetime", "id": "evt_123"}).encode("utf-8")
        ).decode("utf-8")
        resp = await client.get(
            f"/api/projects/prj_cursor_test/events?cursor={bad_ts_b64}",
            headers=founder_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. Founder sees sanitized actor/details (actual actor identity + sanitized details, no raw secrets)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_founder_sees_sanitized_actor_and_details(setup_db, founder_headers):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 17, 0, 0, tzinfo=UTC)

    raw_secret_key = "AIzaSyD-FakeSecretKeyForTesting1234567"

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_founder_view", name="Founder View Proj", repo_path="/repos/fv", status="active"
        )
        session.add(proj)

        evt = AuditEventRecord(
            id="evt_fv_1",
            project_id="prj_founder_view",
            event_type="task_queued",
            task_id="tsk_fv_1",
            actor="founder_ajay",
            details_json={
                "objective": "Implement billing feature",
                "api_key": raw_secret_key,
                "config_mode": "production",
            },
            timestamp=t0,
        )
        session.add(evt)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/projects/prj_founder_view/events", headers=founder_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 1
    event = data["events"][0]

    # Founder sees real actor
    assert event["actor"] == "founder_ajay"

    # Non-sensitive details preserved
    assert event["details"]["objective"] == "Implement billing feature"
    assert event["details"]["config_mode"] == "production"

    # Secret key must NOT be leaked raw
    assert raw_secret_key not in resp.text
    assert event["details"].get("api_key") != raw_secret_key


# ---------------------------------------------------------------------------
# 7. Client sees actor='system' and redacted details (even heavier redaction)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_client_sees_system_actor_and_redacted_details(setup_db, client_headers_factory):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 18, 0, 0, tzinfo=UTC)

    github_pat = "ghp_123456789012345678901234567890123456"
    internal_path = "/Users/ajaytiwari/Desktop/Projects/alphaBrain/internal_kernel.py"

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_client_view", name="Client View Proj", repo_path="/repos/cv", status="active"
        )
        session.add(proj)

        evt = AuditEventRecord(
            id="evt_cv_1",
            project_id="prj_client_view",
            event_type="task_leased",
            task_id="tsk_cv_1",
            actor="wrk_internal_daemon_99",
            details_json={
                "status_summary": "Task processing started",
                "auth_token": github_pat,
                "worktree_path": internal_path,
                "model_telemetry": {
                    "raw_prompt": "Internal system instructions",
                    "input_tokens": 1500,
                    "cost_usd": 0.004,
                },
            },
            timestamp=t0,
        )
        session.add(evt)
        await session.commit()

    headers = client_headers_factory(project_ids=["prj_client_view"], subject="client_org_user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/projects/prj_client_view/events", headers=headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["events"]) == 1
    event = data["events"][0]

    # Client sees actor masked as 'system'
    assert event["actor"] == "system"

    # Public summary is visible
    assert event["details"].get("status_summary") == "Task processing started"

    # Raw secrets and internal paths/telemetry must NOT appear in response body
    assert github_pat not in resp.text
    assert internal_path not in resp.text
    assert "Internal system instructions" not in resp.text


# ---------------------------------------------------------------------------
# 8. Cross-project principal receives 403 with no event leakage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_project_principal_receives_403(setup_db, client_headers_factory):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 19, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        proj_a = ProjectRecord(
            id="prj_secret_a", name="Secret Proj A", repo_path="/repos/a", status="active"
        )
        proj_b = ProjectRecord(
            id="prj_other_b", name="Other Proj B", repo_path="/repos/b", status="active"
        )
        session.add_all([proj_a, proj_b])

        evt = AuditEventRecord(
            id="evt_leak_1",
            project_id="prj_secret_a",
            event_type="task_queued",
            actor="founder_ajay",
            details_json={"classified": "super_confidential_feature"},
            timestamp=t0,
        )
        session.add(evt)
        await session.commit()

    # Principal is ONLY authorized for prj_other_b
    headers = client_headers_factory(project_ids=["prj_other_b"], subject="client_b_user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/projects/prj_secret_a/events", headers=headers)

    assert resp.status_code == 403
    # Verify no events or classified data leaked in error body
    assert "super_confidential_feature" not in resp.text
    assert "evt_leak_1" not in resp.text


# ---------------------------------------------------------------------------
# 9. Unknown project for authorized principal returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_unknown_project_returns_404(setup_db, founder_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/projects/prj_nonexistent_9999/events", headers=founder_headers
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 10. Unknown event type remains visible as category 'work'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_unknown_event_type_mapped_to_work_category(setup_db, founder_headers):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 20, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_unknown_evt", name="Unknown Event Proj", repo_path="/repos/ue", status="active"
        )
        session.add(proj)

        evt = AuditEventRecord(
            id="evt_custom_unknown",
            project_id="prj_unknown_evt",
            event_type="custom_unregistered_agent_signal",
            actor="custom_agent",
            details_json={"custom_data": 42},
            timestamp=t0,
        )
        session.add(evt)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Query unfiltered
        resp = await client.get("/api/projects/prj_unknown_evt/events", headers=founder_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["category"] == "work"
        assert data["events"][0]["event_type"] == "custom_unregistered_agent_signal"

        # Query filtered with category=work
        resp_filtered = await client.get(
            "/api/projects/prj_unknown_evt/events?category=work", headers=founder_headers
        )
        assert resp_filtered.status_code == 200
        data_filtered = resp_filtered.json()
        assert len(data_filtered["events"]) == 1
        assert data_filtered["events"][0]["id"] == "evt_custom_unknown"


# ---------------------------------------------------------------------------
# 11. Raw secret/token/path-like values inserted into audit details never appear in response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_raw_secrets_never_appear_in_response(
    setup_db, founder_headers, client_headers_factory
):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 21, 0, 0, tzinfo=UTC)

    secrets_to_test = [
        "AIzaSyD-GoogleApiKeyShouldBeSanitized999",
        "AQ.Ab8RN6-AjayStitchApiKeyShouldBeSanitized",
        "sk-proj-OpenAIApiKeyShouldBeSanitized123456",
        "ghp_GitHubPersonalAccessTokenShouldBeSanitized1234",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        "super_secret_master_password_value_999",
    ]

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_redact_test", name="Redaction Proj", repo_path="/repos/redact", status="active"
        )
        session.add(proj)

        evt = AuditEventRecord(
            id="evt_redact_1",
            project_id="prj_redact_test",
            event_type="task_queued",
            actor="founder_ajay",
            details_json={
                "google_key": secrets_to_test[0],
                "stitch_key": secrets_to_test[1],
                "openai_key": secrets_to_test[2],
                "github_pat": secrets_to_test[3],
                "bearer_token": secrets_to_test[4],
                "password": secrets_to_test[5],
                "safe_field": "public_description_here",
            },
            timestamp=t0,
        )
        session.add(evt)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check Founder response
        resp_founder = await client.get(
            "/api/projects/prj_redact_test/events", headers=founder_headers
        )
        assert resp_founder.status_code == 200
        for sec in secrets_to_test:
            assert sec not in resp_founder.text, f"Secret leaked in founder view: {sec}"

        # Check Client response
        client_headers = client_headers_factory(project_ids=["prj_redact_test"])
        resp_client = await client.get(
            "/api/projects/prj_redact_test/events", headers=client_headers
        )
        assert resp_client.status_code == 200
        for sec in secrets_to_test:
            assert sec not in resp_client.text, f"Secret leaked in client view: {sec}"


# ---------------------------------------------------------------------------
# 12. Limit boundaries and query validation (default 25, min 1, max 100)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_limit_boundaries_and_query_validation(setup_db, founder_headers):
    session_factory = get_session_factory()
    t0 = datetime(2026, 9, 2, 22, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_limit_test", name="Limit Test Proj", repo_path="/repos/limit", status="active"
        )
        session.add(proj)

        events = [
            AuditEventRecord(
                id=f"evt_lim_{i:03d}",
                project_id="prj_limit_test",
                event_type="task_queued",
                actor="system",
                details_json={},
                timestamp=t0 + timedelta(seconds=i),
            )
            for i in range(1, 35)
        ]
        session.add_all(events)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default limit should be 25
        resp_default = await client.get(
            "/api/projects/prj_limit_test/events", headers=founder_headers
        )
        assert resp_default.status_code == 200
        data_default = resp_default.json()
        assert data_default["returned_count"] == 25
        assert len(data_default["events"]) == 25
        assert data_default["next_cursor"] is not None

        # Min limit boundary: limit=0 -> 422
        resp_zero = await client.get(
            "/api/projects/prj_limit_test/events?limit=0", headers=founder_headers
        )
        assert resp_zero.status_code == 422

        # Max limit boundary: limit=101 -> 422
        resp_over = await client.get(
            "/api/projects/prj_limit_test/events?limit=101", headers=founder_headers
        )
        assert resp_over.status_code == 422

        # Valid custom limit: limit=10
        resp_10 = await client.get(
            "/api/projects/prj_limit_test/events?limit=10", headers=founder_headers
        )
        assert resp_10.status_code == 200
        assert resp_10.json()["returned_count"] == 10


# ---------------------------------------------------------------------------
# 13. Empty project event log returns clean empty response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_empty_project_events_returns_clean_response(setup_db, founder_headers):
    session_factory = get_session_factory()
    async with session_factory() as session:
        proj = ProjectRecord(
            id="prj_empty_test", name="Empty Proj", repo_path="/repos/empty", status="active"
        )
        session.add(proj)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/projects/prj_empty_test/events", headers=founder_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []
    assert data["next_cursor"] is None
    assert data["returned_count"] == 0


# ---------------------------------------------------------------------------
# 14. Unauthenticated or invalid token requests return 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_unauthenticated_request_rejected(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing auth header
        resp1 = await client.get("/api/projects/prj_any/events")
        assert resp1.status_code == 401

        # Invalid token
        resp2 = await client.get(
            "/api/projects/prj_any/events", headers={"Authorization": "Bearer invalid-token-xyz"}
        )
        assert resp2.status_code == 401
