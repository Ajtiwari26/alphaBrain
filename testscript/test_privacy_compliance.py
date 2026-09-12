from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import (
    AttemptRecord,
    AuditEventRecord,
    CallJobRecord,
    CallStatusRecord,
    ConsentRecord,
    MeetingParticipantRecord,
    MeetingRecord,
    OrganizationRecord,
    ProjectRecord,
    TaskCheckpointRecord,
    TaskRecord,
    TranscriptSegmentRecord,
    UserRecord,
    WorkerHealthRecord,
    WorkerRecord,
)
from alpha_core.privacy.engine import (
    ConsentManager,
    RTBFManager,
    TelephonyConsentValidator,
)
from alpha_core.privacy.enums import ConsentType, DataClass
from alpha_core.privacy.models import (
    ConsentRecordRequest,
    ConsentWithdrawalRequest,
)
from alpha_core.security import PrincipalRole, create_scoped_principal_token


@pytest.fixture
def auth_headers(api_headers):
    return api_headers


@pytest.mark.asyncio
async def test_consent_tracking_and_withdrawal_endpoints(setup_db, auth_headers):
    """Verifies consent recording, querying, and withdrawal via REST endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Validation error when neither user_id nor phone_number provided
        invalid_resp = await client.post(
            "/api/v1/privacy/consent",
            json={"consent_type": "voice_recording", "granted": True},
            headers=auth_headers,
        )
        assert invalid_resp.status_code == 400

        # 2. Record telephonic outreach consent
        consent_payload = {
            "user_id": "usr_test_101",
            "phone_number": "+14155552671",
            "project_id": "prj_alpha_1",
            "consent_type": ConsentType.TELEPHONIC_OUTREACH.value,
            "granted": True,
            "ip_address": "198.51.100.1",
            "user_agent": "Mozilla/5.0 TestBrowser",
            "metadata": {"source": "onboarding_modal"},
        }
        res = await client.post(
            "/api/v1/privacy/consent", json=consent_payload, headers=auth_headers
        )
        assert res.status_code == 201
        data = res.json()
        assert data["user_id"] == "usr_test_101"
        assert data["phone_number"] == "+14155552671"
        assert data["consent_type"] == ConsentType.TELEPHONIC_OUTREACH.value
        assert data["granted"] is True
        assert data["revoked_at"] is None
        assert data["metadata"]["source"] == "onboarding_modal"

        # 3. Record voice recording consent for the same user
        rec_payload = {
            "user_id": "usr_test_101",
            "phone_number": "+14155552671",
            "project_id": "prj_alpha_1",
            "consent_type": ConsentType.VOICE_RECORDING.value,
            "granted": True,
        }
        res2 = await client.post("/api/v1/privacy/consent", json=rec_payload, headers=auth_headers)
        assert res2.status_code == 201

        # 4. Query consents by user_id
        list_res = await client.get(
            "/api/v1/privacy/consent?user_id=usr_test_101", headers=auth_headers
        )
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] == 2

        # 5. Query active only
        active_res = await client.get(
            "/api/v1/privacy/consent?phone_number=%2B14155552671&active_only=true",
            headers=auth_headers,
        )
        assert active_res.status_code == 200
        assert active_res.json()["total"] == 2

        # 6. Withdraw single consent type via POST /consent/withdraw
        withdraw_payload = {
            "phone_number": "+14155552671",
            "consent_type": ConsentType.VOICE_RECORDING.value,
            "reason": "User requested opt-out of voice recording",
        }
        w_res = await client.post(
            "/api/v1/privacy/consent/withdraw", json=withdraw_payload, headers=auth_headers
        )
        assert w_res.status_code == 200
        w_data = w_res.json()
        assert w_data["total"] == 1
        withdrawn_rec = w_data["consents"][0]
        assert withdrawn_rec["consent_type"] == ConsentType.VOICE_RECORDING.value
        assert withdrawn_rec["granted"] is False
        assert withdrawn_rec["revoked_at"] is not None
        assert (
            withdrawn_rec["metadata"]["withdrawal_reason"]
            == "User requested opt-out of voice recording"
        )

        # 7. Verify active count is now 1
        active_after = await client.get(
            "/api/v1/privacy/consent?user_id=usr_test_101&active_only=true",
            headers=auth_headers,
        )
        assert active_after.json()["total"] == 1

        # 8. Withdraw remaining consent via DELETE /consent
        del_res = await client.delete(
            "/api/v1/privacy/consent?phone_number=%2B14155552671&reason=Account+closure",
            headers=auth_headers,
        )
        assert del_res.status_code == 200
        assert del_res.json()["total"] == 1

        # 9. Verify active count is now 0
        active_final = await client.get(
            "/api/v1/privacy/consent?user_id=usr_test_101&active_only=true",
            headers=auth_headers,
        )
        assert active_final.json()["total"] == 0


@pytest.mark.asyncio
async def test_right_to_be_forgotten_export_and_deletion(setup_db, auth_headers):
    """Verifies GDPR/CCPA export and deletion lifecycle with audit guarantees."""
    session_factory = get_session_factory()
    test_user_id = "usr_rtbf_99"
    test_email = "alex.founder@startup.io"
    test_phone = "+14159876543"

    async with session_factory() as session:
        # Seed user
        org = OrganizationRecord(id="org_rtbf_1", name="RTBF Corp", slug="rtbf-corp")
        session.add(org)
        user = UserRecord(
            id=test_user_id,
            org_id="org_rtbf_1",
            name="Alex Founder",
            email=test_email,
            role="founder",
        )
        session.add(user)

        # Seed project
        proj = ProjectRecord(
            id="prj_rtbf_1",
            org_id="org_rtbf_1",
            name="Alpha AI",
            repo_path="/tmp/repo",
        )
        session.add(proj)

        # Seed consent
        consent = ConsentRecord(
            id="cst_rtbf_1",
            user_id=test_user_id,
            phone_number=test_phone,
            consent_type="ai_processing",
            granted=True,
            ip_address="203.0.113.10",
            user_agent="AgentApp/1.0",
        )
        session.add(consent)

        # Seed call job
        call_job = CallJobRecord(
            id="call_rtbf_1",
            notification_id="ntf_rtbf_1",
            recipient_phone=test_phone,
            recipient_name="Alex Founder",
            purpose="preview_alert",
            script_facts_json={"milestone": "M1"},
            idempotency_key="idem_rtbf_1",
        )
        session.add(call_job)

        # Seed meeting, participant, and transcript
        meeting = MeetingRecord(
            id="mtg_rtbf_1",
            project_id="prj_rtbf_1",
            room_name="rtbf-spec-review",
        )
        session.add(meeting)

        part = MeetingParticipantRecord(
            id="prt_rtbf_1",
            meeting_id="mtg_rtbf_1",
            identity=test_user_id,
            name="Alex Founder",
        )
        session.add(part)

        seg = TranscriptSegmentRecord(
            id="seg_rtbf_1",
            meeting_id="mtg_rtbf_1",
            speaker_identity=test_user_id,
            speaker_name="Alex Founder",
            text="I approve the specifications and confidential architecture plan.",
        )
        session.add(seg)

        # Audit event
        audit = AuditEventRecord(
            id="aud_rtbf_prev",
            event_type="user.login",
            actor=test_user_id,
            details_json={"ip": "203.0.113.10"},
        )
        session.add(audit)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Export personal data via GET
        exp_res = await client.get(
            f"/api/v1/privacy/export?user_id={test_user_id}", headers=auth_headers
        )
        assert exp_res.status_code == 200
        export_data = exp_res.json()
        assert export_data["subject_id"] == test_user_id
        assert export_data["user_profile"]["email"] == test_email
        assert len(export_data["consents"]) == 1
        assert len(export_data["call_jobs"]) == 1
        assert len(export_data["transcript_segments"]) == 1
        assert "confidential architecture plan" in export_data["transcript_segments"][0]["text"]

        # 2. Export via POST
        exp_post = await client.post(
            "/api/v1/privacy/export",
            json={"phone_number": test_phone},
            headers=auth_headers,
        )
        assert exp_post.status_code == 200
        assert len(exp_post.json()["call_jobs"]) == 1

        # 3. RTBF Deletion / Anonymization via POST
        del_payload = {
            "user_id": test_user_id,
            "phone_number": test_phone,
            "email": test_email,
            "reason": "GDPR Article 17 Erasure Request",
        }
        del_res = await client.post(
            "/api/v1/privacy/delete", json=del_payload, headers=auth_headers
        )
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert del_data["status"] == "completed"
        assert del_data["records_affected"]["users_anonymized"] == 1
        assert del_data["records_affected"]["consents_revoked"] == 1
        assert del_data["records_affected"]["transcripts_redacted"] == 1
        assert del_data["records_affected"]["call_jobs_redacted"] == 1
        audit_event_id = del_data["audit_event_id"]
        assert audit_event_id.startswith("aud_")

    # 4. Verify database state directly
    async with session_factory() as session:
        # Check User Record is anonymized
        u = await session.get(UserRecord, test_user_id)
        assert u.name == "[REDACTED]"
        assert u.is_active is False
        assert u.deleted_at is not None
        assert "@deleted.local" in u.email

        # Check Consent is revoked and scrubbed
        c = await session.get(ConsentRecord, "cst_rtbf_1")
        assert c.granted is False
        assert c.revoked_at is not None
        assert c.ip_address == "0.0.0.0"
        assert c.user_agent == "[REDACTED]"

        # Check Call Job is redacted
        cj = await session.get(CallJobRecord, "call_rtbf_1")
        assert cj.recipient_phone == "[REDACTED]"
        assert cj.recipient_name == "[REDACTED]"
        assert cj.script_facts_json == {}

        # Check Transcript is redacted
        tr = await session.get(TranscriptSegmentRecord, "seg_rtbf_1")
        assert tr.speaker_name == "[REDACTED]"
        assert tr.speaker_identity != test_user_id
        assert tr.speaker_identity.startswith("redacted_")
        assert "[REDACTED PURSUANT TO DATA PRIVACY RTBF REQUEST]" in tr.text

        # Check immutable AuditEvent exists
        aud = await session.get(AuditEventRecord, audit_event_id)
        assert aud is not None
        assert aud.event_type == "privacy.rtbf_deletion"
        assert aud.details_json["reason"] == "GDPR Article 17 Erasure Request"


@pytest.mark.asyncio
async def test_automated_data_retention_lifecycle(setup_db, auth_headers):
    """Verifies retention lifecycle pruning by data class based on configurable TTLs."""
    session_factory = get_session_factory()
    now = datetime.now(UTC)

    async with session_factory() as session:
        # 1. Worker Health: TTL 7 days
        worker = WorkerRecord(id="wrk_ret_1", hostname="worker-retention")
        session.add(worker)
        # Old record (10 days old -> should be pruned)
        wh_old = WorkerHealthRecord(
            id="wh_old_1",
            worker_id="wrk_ret_1",
            reported_at=now - timedelta(days=10),
        )
        # Fresh record (2 days old -> should remain)
        wh_fresh = WorkerHealthRecord(
            id="wh_fresh_1",
            worker_id="wrk_ret_1",
            reported_at=now - timedelta(days=2),
        )
        session.add_all([wh_old, wh_fresh])

        # 2. Task Checkpoints: TTL 14 days
        proj_chk = ProjectRecord(id="prj_chk_1", name="Checkpoint Proj", repo_path="/tmp/repo")
        session.add(proj_chk)
        task_chk = TaskRecord(
            id="tsk_chk_ret",
            project_id="prj_chk_1",
            objective="Retention check",
            repo="alpha/repo",
            status="leased",
            preferred_agent="antigravity",
            risk_class="low",
            max_attempts=3,
            details_json={},
        )
        session.add(task_chk)
        att_chk = AttemptRecord(
            id="att_chk_ret",
            task_id="tsk_chk_ret",
            agent="antigravity",
            model="gemini-3.1-pro",
        )
        session.add(att_chk)

        chk_old = TaskCheckpointRecord(
            id="chk_old_1",
            task_id="tsk_chk_ret",
            attempt_id="att_chk_ret",
            worker_id="wrk_ret_1",
            attempt_number=1,
            sequence=1,
            project_id="prj_chk_1",
            repo_reference="alpha/repo",
            base_commit="abc1234",
            worktree_path="/tmp/wt1",
            worktree_head="def5678",
            conversation_id="conv_chk_1",
            execution_stage="stage",
            lease_token_hash="hash_old",
            side_effect_state="none",
            scrubbed_payload={},
            payload_digest="dig1",
            idempotency_key="idm1",
            created_at=now - timedelta(days=20),
        )
        chk_fresh = TaskCheckpointRecord(
            id="chk_fresh_1",
            task_id="tsk_chk_ret",
            attempt_id="att_chk_ret",
            worker_id="wrk_ret_1",
            attempt_number=1,
            sequence=2,
            project_id="prj_chk_1",
            repo_reference="alpha/repo",
            base_commit="abc1234",
            worktree_path="/tmp/wt2",
            worktree_head="def5678",
            conversation_id="conv_chk_2",
            execution_stage="stage",
            lease_token_hash="hash_fresh",
            side_effect_state="none",
            scrubbed_payload={},
            payload_digest="dig2",
            idempotency_key="idm2",
            created_at=now - timedelta(days=3),
        )
        session.add_all([chk_old, chk_fresh])

        # 3. Transcripts: TTL 30 days
        proj = ProjectRecord(id="prj_mtg_1", name="Project Mtg", repo_path="/tmp")
        session.add(proj)
        mtg = MeetingRecord(id="mtg_1", project_id="prj_mtg_1", room_name="room-1")
        session.add(mtg)

        tr_old = TranscriptSegmentRecord(
            id="tr_old_1",
            meeting_id="mtg_1",
            speaker_identity="usr_bob",
            speaker_name="Bob",
            text="Old discussion",
            timestamp=now - timedelta(days=45),
        )
        tr_fresh = TranscriptSegmentRecord(
            id="tr_fresh_1",
            meeting_id="mtg_1",
            speaker_identity="usr_bob",
            speaker_name="Bob",
            text="Recent discussion",
            timestamp=now - timedelta(days=5),
        )
        session.add_all([tr_old, tr_fresh])

        # 4. Call records: TTL 90 days
        cj_old = CallJobRecord(
            id="cj_old_1",
            notification_id="ntf_1",
            recipient_phone="+1000000001",
            purpose="test",
            status="completed",
            duration_seconds=30,
            idempotency_key="idem_old",
            created_at=now - timedelta(days=120),
        )
        cs_old = CallStatusRecord(
            id="cs_old_1",
            call_job_id="cj_old_1",
            status="completed",
        )
        cj_fresh = CallJobRecord(
            id="cj_fresh_1",
            notification_id="ntf_2",
            recipient_phone="+1000000002",
            purpose="test",
            status="completed",
            duration_seconds=45,
            idempotency_key="idem_fresh",
            created_at=now - timedelta(days=10),
        )
        session.add_all([cj_old, cs_old, cj_fresh])

        # 5. Revoked consents: TTL 180 days
        cst_revoked_old = ConsentRecord(
            id="cst_rev_old",
            phone_number="+1000000003",
            consent_type="telephonic_outreach",
            granted=False,
            revoked_at=now - timedelta(days=200),
        )
        cst_revoked_fresh = ConsentRecord(
            id="cst_rev_fresh",
            phone_number="+1000000004",
            consent_type="telephonic_outreach",
            granted=False,
            revoked_at=now - timedelta(days=15),
        )
        session.add_all([cst_revoked_old, cst_revoked_fresh])

        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check policy metadata endpoint
        pol_res = await client.get("/api/v1/privacy/retention/policies", headers=auth_headers)
        assert pol_res.status_code == 200
        policies = pol_res.json()["ttls_days"]
        assert policies[DataClass.WORKER_HEALTH.value] == 7
        assert policies[DataClass.TRANSCRIPTS.value] == 30

        # Run Dry-Run Pruning
        dry_res = await client.post(
            "/api/v1/privacy/retention/prune",
            json={"dry_run": True},
            headers=auth_headers,
        )
        assert dry_res.status_code == 200
        dry_data = dry_res.json()
        assert dry_data["dry_run"] is True
        assert dry_data["pruned_counts"][DataClass.WORKER_HEALTH.value] == 1
        assert dry_data["pruned_counts"][DataClass.TASK_CHECKPOINTS.value] == 1
        assert dry_data["pruned_counts"][DataClass.TRANSCRIPTS.value] == 1
        assert dry_data["pruned_counts"][DataClass.CALL_RECORDS.value] == 1
        assert dry_data["pruned_counts"][DataClass.REVOKED_CONSENTS.value] == 1

        # Run Real Pruning
        prune_res = await client.post(
            "/api/v1/privacy/retention/prune",
            json={"dry_run": False},
            headers=auth_headers,
        )
        assert prune_res.status_code == 200
        prune_data = prune_res.json()
        assert prune_data["dry_run"] is False
        assert prune_data["total_pruned"] == 5

    # Verify DB state after pruning
    async with session_factory() as session:
        # Worker health: old deleted, fresh kept
        assert await session.get(WorkerHealthRecord, "wh_old_1") is None
        assert await session.get(WorkerHealthRecord, "wh_fresh_1") is not None

        # Checkpoints: old deleted, fresh kept
        assert await session.get(TaskCheckpointRecord, "chk_old_1") is None
        assert await session.get(TaskCheckpointRecord, "chk_fresh_1") is not None

        # Transcripts: old deleted, fresh kept
        assert await session.get(TranscriptSegmentRecord, "tr_old_1") is None
        assert await session.get(TranscriptSegmentRecord, "tr_fresh_1") is not None

        # Call records: old deleted, fresh kept
        assert await session.get(CallJobRecord, "cj_old_1") is None
        assert await session.get(CallStatusRecord, "cs_old_1") is None
        assert await session.get(CallJobRecord, "cj_fresh_1") is not None

        # Revoked consents: old deleted, fresh kept
        assert await session.get(ConsentRecord, "cst_rev_old") is None
        assert await session.get(ConsentRecord, "cst_rev_fresh") is not None


@pytest.mark.asyncio
async def test_telephony_consent_and_disclosure_validation(setup_db, auth_headers):
    """Verifies telephony consent and statutory disclosure validation."""
    test_phone = "+14155559876"
    test_project = "prj_telephony_alpha"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Validation fails when recipient phone is empty
        empty_res = await client.post(
            "/api/v1/privacy/telephony/validate",
            json={"recipient_phone": "   "},
            headers=auth_headers,
        )
        assert empty_res.status_code == 200
        assert empty_res.json()["allowed"] is False
        assert "empty" in empty_res.json()["rejection_reason"]

        # 2. Validation fails when statutory disclosure is NOT acknowledged
        no_disclosure = await client.post(
            "/api/v1/privacy/telephony/validate",
            json={"recipient_phone": test_phone, "disclosure_acknowledged": False},
            headers=auth_headers,
        )
        assert no_disclosure.status_code == 200
        assert no_disclosure.json()["allowed"] is False
        assert "disclosure was not acknowledged" in no_disclosure.json()["rejection_reason"]

        # 3. Validation fails when no consent exists on file
        no_consent = await client.post(
            "/api/v1/privacy/telephony/validate",
            json={"recipient_phone": test_phone, "disclosure_acknowledged": True},
            headers=auth_headers,
        )
        assert no_consent.status_code == 200
        assert no_consent.json()["allowed"] is False
        assert "No active telephonic outreach consent" in no_consent.json()["rejection_reason"]

        # 4. Grant telephonic_outreach consent
        await client.post(
            "/api/v1/privacy/consent",
            json={
                "phone_number": test_phone,
                "project_id": test_project,
                "consent_type": ConsentType.TELEPHONIC_OUTREACH.value,
                "granted": True,
            },
            headers=auth_headers,
        )

        # 5. Validation fails when recording consent required but not yet granted
        rec_missing = await client.post(
            "/api/v1/privacy/telephony/validate",
            json={
                "recipient_phone": test_phone,
                "project_id": test_project,
                "require_recording_consent": True,
                "disclosure_acknowledged": True,
            },
            headers=auth_headers,
        )
        assert rec_missing.json()["allowed"] is False
        assert "Voice recording consent missing" in rec_missing.json()["rejection_reason"]

        # 6. Grant voice_recording consent
        await client.post(
            "/api/v1/privacy/consent",
            json={
                "phone_number": test_phone,
                "project_id": test_project,
                "consent_type": ConsentType.VOICE_RECORDING.value,
                "granted": True,
            },
            headers=auth_headers,
        )

        # 7. Validation succeeds via POST
        valid_post = await client.post(
            "/api/v1/privacy/telephony/validate",
            json={
                "recipient_phone": test_phone,
                "project_id": test_project,
                "require_recording_consent": True,
                "disclosure_acknowledged": True,
            },
            headers=auth_headers,
        )
        assert valid_post.status_code == 200
        valid_post_data = valid_post.json()
        assert valid_post_data["allowed"] is True
        assert valid_post_data["disclosure_verified"] is True
        assert valid_post_data["rejection_reason"] is None
        assert valid_post_data["consent_id"] is not None

        # 8. Validation succeeds via GET
        valid_get = await client.get(
            f"/api/v1/privacy/telephony/validate?recipient_phone=%2B14155559876&project_id={test_project}",
            headers=auth_headers,
        )
        assert valid_get.status_code == 200
        assert valid_get.json()["allowed"] is True

        # 9. Withdraw telephonic outreach consent
        await client.post(
            "/api/v1/privacy/consent/withdraw",
            json={
                "phone_number": test_phone,
                "consent_type": ConsentType.TELEPHONIC_OUTREACH.value,
                "reason": "Revocation test",
            },
            headers=auth_headers,
        )

        # 10. Validation fails due to revoked consent
        revoked_val = await client.post(
            "/api/v1/privacy/telephony/validate",
            json={
                "recipient_phone": test_phone,
                "project_id": test_project,
                "disclosure_acknowledged": True,
            },
            headers=auth_headers,
        )
        assert revoked_val.json()["allowed"] is False
        assert "revoked at" in revoked_val.json()["rejection_reason"]


@pytest.mark.asyncio
async def test_direct_engine_methods(setup_db):
    """Tests the privacy engine classes directly for 100% unit test coverage."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        # Test ConsentManager.has_active_consent
        has_c = await ConsentManager.has_active_consent(
            session,
            consent_type="ai_processing",
            phone_number="+18885551234",
        )
        assert has_c is False

        # Record consent via engine
        req = ConsentRecordRequest(
            phone_number="+18885551234",
            consent_type="ai_processing",
            granted=True,
            metadata={"source": "engine_direct"},
        )
        c_res = await ConsentManager.record_consent(session, req)
        assert c_res.granted is True

        # Check has_active_consent again
        has_c2 = await ConsentManager.has_active_consent(
            session,
            consent_type="ai_processing",
            phone_number="+18885551234",
        )
        assert has_c2 is True

        # Withdraw without identifier raises ValueError
        with pytest.raises(ValueError, match="Must provide user_id or phone_number"):
            await ConsentManager.withdraw_consent(session, ConsentWithdrawalRequest())

        # Test RTBFManager export with unknown user
        exp_unknown = await RTBFManager.export_user_data(session, user_id="usr_nonexistent")
        assert exp_unknown.user_profile is None
        assert exp_unknown.consents == []

        # Test TelephonyConsentValidator directly
        t_val = await TelephonyConsentValidator.validate_telephony_consent(
            session,
            recipient_phone="+18885551234",
            require_recording_consent=False,
            disclosure_acknowledged=True,
        )
        assert t_val.allowed is False


@pytest.mark.asyncio
async def test_auth_bypass_and_idor_protection(setup_db):
    """Verifies that all privacy endpoints enforce authentication and block IDOR attacks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Unauthenticated requests are rejected with 401
        res1 = await client.get("/api/v1/privacy/consent?user_id=usr_alice")
        assert res1.status_code == 401

        res2 = await client.get("/api/v1/privacy/export?user_id=usr_alice")
        assert res2.status_code == 401

        res3 = await client.delete("/api/v1/privacy/delete?user_id=usr_alice")
        assert res3.status_code == 401

        res4 = await client.post("/api/v1/privacy/retention/prune", json={})
        assert res4.status_code == 401

        # 2. Client principal authentication
        alice_token = create_scoped_principal_token(
            subject="usr_alice",
            role=PrincipalRole.CLIENT,
            project_ids=["prj_alice_app"],
        )
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        # Alice accessing Alice's own data -> 200
        alice_export = await client.get(
            "/api/v1/privacy/export?user_id=usr_alice",
            headers=alice_headers,
        )
        assert alice_export.status_code == 200

        # Alice attempting IDOR attack on Bob's data -> 403 Forbidden
        bob_export_attack = await client.get(
            "/api/v1/privacy/export?user_id=usr_bob",
            headers=alice_headers,
        )
        assert bob_export_attack.status_code == 403
        assert "not authorized" in bob_export_attack.json()["detail"]

        # Alice attempting IDOR deletion of Bob's data -> 403 Forbidden
        bob_delete_attack = await client.delete(
            "/api/v1/privacy/delete?user_id=usr_bob",
            headers=alice_headers,
        )
        assert bob_delete_attack.status_code == 403
        assert "not authorized" in bob_delete_attack.json()["detail"]

        # Alice attempting to trigger administrative retention pruning -> 403 Forbidden
        alice_prune_attack = await client.post(
            "/api/v1/privacy/retention/prune",
            json={},
            headers=alice_headers,
        )
        assert alice_prune_attack.status_code == 403
        assert "administrative role required" in alice_prune_attack.json()["detail"]
