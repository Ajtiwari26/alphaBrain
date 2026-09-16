"""
testscript/test_delivery_board_and_delegates.py
Verification suite for Amazon-Style Delivery Board, Executive Reading Room,
Delegate ID/Passcode system, and Admin Pipeline Handover governance.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from alpha_core.mobile_bridge.api import create_mobile_bridge_app  # noqa: E402
from alpha_core.mobile_bridge.schemas import (  # noqa: E402
    AdminFeedbackVerdictRequest,
    DelegateAuthRequest,
    DelegateInviteRequest,
    FeedbackCreateRequest,
)
from alpha_core.mobile_bridge.service import MobileBridgeService  # noqa: E402
from alpha_core.queue.triage_queue import DEFAULT_DB_PATH, TaskTriageQueue  # noqa: E402
from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal  # noqa: E402


class TestDeliveryBoardAndDelegates(unittest.TestCase):
    def setUp(self):
        self.service = MobileBridgeService()
        self.queue = TaskTriageQueue(DEFAULT_DB_PATH)

    def test_01_delivery_map_structure(self):
        """Verify Amazon-style 7-stage sequential delivery map."""
        delivery_map = self.service.get_delivery_map(project_id="alphabrain_dogfood")
        self.assertEqual(delivery_map.total_steps, 7)
        self.assertEqual(len(delivery_map.stages), 7)
        self.assertGreaterEqual(delivery_map.overall_progress_percent, 0)
        self.assertLessEqual(delivery_map.overall_progress_percent, 100)

        stage_titles = [s.title for s in delivery_map.stages]
        self.assertIn("Inception & Triage Ingestion", stage_titles)
        self.assertIn("Deterministic Safety Gate", stage_titles)
        self.assertIn("Senior Planning Consensus", stage_titles)
        self.assertIn("Isolated Worktree Worker", stage_titles)
        self.assertIn("2-Round Adversarial Review", stage_titles)
        self.assertIn("Atomic Fast-Forward Merge", stage_titles)
        self.assertIn("Production Telemetry & Delivery", stage_titles)

        # Check badges and actors
        for s in delivery_map.stages:
            self.assertTrue(bool(s.checkpoint_badge))
            self.assertTrue(bool(s.actor))
            self.assertIn(s.status, {"completed", "in_transit", "pending"})

    def test_02_executive_reading_room(self):
        """Verify documentation indexing and read-only Senior Directive access."""
        docs = self.service.list_executive_docs()
        self.assertGreaterEqual(len(docs), 3)

        doc_ids = {d.doc_id: d for d in docs}
        self.assertIn("senior_directive", doc_ids)
        self.assertIn("next_phase_roadmap", doc_ids)
        self.assertIn("mobile_screens_spec", doc_ids)

        # Verify Senior Directive content and read-only author
        directive = self.service.get_executive_doc("senior_directive")
        self.assertIn("Claude Opus", directive.author)
        self.assertGreater(len(directive.content_markdown), 5000)
        self.assertGreater(len(directive.sections), 5)

    def test_03_delegate_credentials_and_admin_access(self):
        """Verify delegate creation, passcode matching, and admin delegation."""
        # Create standard client viewer
        client_invite = DelegateInviteRequest(
            member_name="Test Partner Corp",
            role="client_viewer",
            grant_admin_access=False,
        )
        client_cred = self.service.create_delegate_invite(client_invite)
        self.assertTrue(client_cred.delegate_id.startswith("CLT-"))
        self.assertTrue(client_cred.passcode.startswith("ALPHA-"))
        self.assertFalse(client_cred.can_admin_verdict)

        # Create delegated admin
        admin_invite = DelegateInviteRequest(
            member_name="VP Engineering Delegate",
            role="team_delegate",
            grant_admin_access=True,
        )
        admin_cred = self.service.create_delegate_invite(admin_invite)
        self.assertTrue(admin_cred.delegate_id.startswith("ADM-"))
        self.assertTrue(admin_cred.can_admin_verdict)

        # Authenticate client
        auth_resp = self.service.authenticate_delegate(
            DelegateAuthRequest(
                delegate_id=client_cred.delegate_id,
                passcode=client_cred.passcode,
            )
        )
        self.assertTrue(auth_resp.authenticated)
        self.assertFalse(auth_resp.can_admin_verdict)

        # Authenticate admin
        admin_auth_resp = self.service.authenticate_delegate(
            DelegateAuthRequest(
                delegate_id=admin_cred.delegate_id,
                passcode=admin_cred.passcode,
            )
        )
        self.assertTrue(admin_auth_resp.authenticated)
        self.assertTrue(admin_auth_resp.can_admin_verdict)

    def test_04_feedback_submission_and_eva_analysis(self):
        """Verify client feedback ingestion triggers Eva's real-time diagnostic synthesis."""
        fb_req = FeedbackCreateRequest(
            author_name="Acme QA Lead",
            author_role="Client Delegate",
            problem_title="Automated Test: Verify telemetry stream latency",
            problem_description="Observed periodic lag on WebRTC audio codec initialization.",
        )
        item = self.service.submit_feedback(fb_req, project_id="alphabrain_dogfood")
        self.assertTrue(item.id.startswith("fb_"))
        self.assertEqual(item.status, "pending_admin")
        self.assertIn("Eva AI Diagnostic", str(item.eva_analysis))
        self.assertIsNotNone(item.eva_proposed_task)

    def test_05_strict_admin_handover_to_orchestration(self):
        """Verify that Admin Handover admits a real task into TaskTriageQueue."""
        # 1. Submit ticket
        item = self.service.submit_feedback(
            FeedbackCreateRequest(
                author_name="Chief Architect",
                author_role="Client Delegate",
                problem_title="Critical: Add p99 latency SLA check",
                problem_description="Need automated verification of live p99 latency.",
            )
        )

        # 2. Founder / Admin approves handover
        verdict = AdminFeedbackVerdictRequest(
            action="handover_pipeline",
            admin_notes="Approved by Founder for autonomous worktree worker dispatch.",
            reviewer_name="Founder",
        )
        founder_principal = AuthPrincipal(subject="Ajay Founder", role=PrincipalRole.FOUNDER)
        updated = self.service.admin_verdict_on_feedback(item.id, verdict, principal=founder_principal)
        self.assertEqual(updated.status, "handed_over")
        self.assertIsNotNone(updated.admitted_task_id)
        self.assertEqual(updated.reviewed_by, "Ajay Founder")

        # 3. Verify task exists in SQLite triage queue!
        tasks = self.queue.list_tasks(limit=10)
        found_task = next((t for t in tasks if str(t.get("id")) == updated.admitted_task_id), None)
        self.assertIsNotNone(found_task)
        self.assertIn("Critical: Add p99 latency SLA check", str(found_task.get("title") or found_task.get("envelope_json")))

    def test_06_delegate_passcode_masking(self):
        """Verify Repair Directive R-3: passcodes are masked in delegate listings."""
        # Seed an invite
        invite = DelegateInviteRequest(
            member_name="SecOps Auditor",
            role="client_viewer",
            grant_admin_access=False,
        )
        cred = self.service.create_delegate_invite(invite)
        # Cleartext returned upon generation so admin can convey it
        self.assertTrue(cred.passcode.startswith("ALPHA-"))
        self.assertNotIn("****", cred.passcode)

        # Listing masks all passcodes
        listed = self.service.list_delegates(mask_passcode=True)
        self.assertGreaterEqual(len(listed), 1)
        for d in listed:
            self.assertTrue(d.passcode.endswith("****") or d.passcode == "******")

        # DelegateCredential.masked() helper unit check
        masked_cred = cred.masked()
        self.assertTrue(masked_cred.passcode.endswith("****"))
        self.assertEqual(masked_cred.delegate_id, cred.delegate_id)

    def test_07_service_admin_verdict_auth_principal_validation(self):
        """Verify Repair Directive R-2: Invariant I-1 validation in service layer."""
        # 1. Create a feedback item
        item = self.service.submit_feedback(
            FeedbackCreateRequest(
                author_name="Auditor Delegate",
                problem_title="Security Audit: Admin verdict unauthorized test",
                problem_description="Verifying that non-admin principals cannot execute verdicts.",
            )
        )

        verdict = AdminFeedbackVerdictRequest(
            action="dismiss_rejected",
            admin_notes="Attempted dismissal by unauthorized role.",
        )

        # 2. Client principal attempt must raise PermissionError (Fail-Closed)
        unauthorized_principal = AuthPrincipal(subject="client_user", role=PrincipalRole.CLIENT)
        with self.assertRaises(PermissionError):
            self.service.admin_verdict_on_feedback(item.id, verdict, principal=unauthorized_principal)

        # 3. Worker principal attempt must raise PermissionError
        worker_principal = AuthPrincipal(subject="worker_daemon", role=PrincipalRole.WORKER)
        with self.assertRaises(PermissionError):
            self.service.admin_verdict_on_feedback(item.id, verdict, principal=worker_principal)

        # 4. Founder principal must succeed and record authentic reviewer
        founder_principal = AuthPrincipal(subject="Founder Ajay", role=PrincipalRole.FOUNDER)
        resolved_item = self.service.admin_verdict_on_feedback(item.id, verdict, principal=founder_principal)
        self.assertEqual(resolved_item.status, "rejected")
        self.assertEqual(resolved_item.reviewed_by, "Founder Ajay")

        # 5. Delegated admin principal must also succeed
        admin_principal = AuthPrincipal(subject="VP Eng Delegate", role=PrincipalRole.ADMIN)
        verdict_direct = AdminFeedbackVerdictRequest(
            action="resolve_direct",
            admin_notes="Directly clarified by Delegated Admin.",
        )
        direct_item = self.service.admin_verdict_on_feedback(item.id, verdict_direct, principal=admin_principal)
        self.assertEqual(direct_item.status, "resolved")
        self.assertEqual(direct_item.reviewed_by, "VP Eng Delegate")

    def test_08_api_endpoints_role_guards(self):
        """Verify Repair Directive R-1: Depends(require_api_principal) and Invariant I-1 on API routes."""
        app = create_mobile_bridge_app()
        client = TestClient(app)

        # Create a feedback item to act upon
        item = self.service.submit_feedback(
            FeedbackCreateRequest(
                author_name="API Tester",
                problem_title="API Role Guard Test",
                problem_description="Testing HTTP 403 on client role and 200 on admin role.",
            )
        )

        # Case A: POST /feedback/{id}/admin-verdict with CLIENT role -> 403 Forbidden
        app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
            subject="client_viewer_1", role=PrincipalRole.CLIENT
        )
        res_client = client.post(
            f"/api/v1/mobile/feedback/{item.id}/admin-verdict",
            json={"action": "dismiss_rejected", "admin_notes": "Client attempting verdict"},
        )
        self.assertEqual(res_client.status_code, 403)
        self.assertIn("Invariant I-1", res_client.json()["detail"])

        # Case B: POST /feedback/{id}/admin-verdict with FOUNDER role -> 200 OK
        app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
            subject="ajay_founder", role=PrincipalRole.FOUNDER
        )
        res_founder = client.post(
            f"/api/v1/mobile/feedback/{item.id}/admin-verdict",
            json={"action": "resolve_direct", "admin_notes": "Founder direct resolution"},
        )
        self.assertEqual(res_founder.status_code, 200)
        self.assertEqual(res_founder.json()["status"], "resolved")
        self.assertEqual(res_founder.json()["reviewed_by"], "ajay_founder")

        # Case C: POST /delegates/invite with CLIENT role -> 403 Forbidden
        app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
            subject="client_viewer_1", role=PrincipalRole.CLIENT
        )
        res_invite_fail = client.post(
            "/api/v1/mobile/delegates/invite",
            json={"member_name": "Unauthorized Delegate", "role": "client_viewer"},
        )
        self.assertEqual(res_invite_fail.status_code, 403)

        # Case D: POST /delegates/invite with ADMIN role -> 200 OK
        app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
            subject="admin_user", role=PrincipalRole.ADMIN
        )
        res_invite_ok = client.post(
            "/api/v1/mobile/delegates/invite",
            json={"member_name": "New Delegate", "role": "client_viewer"},
        )
        self.assertEqual(res_invite_ok.status_code, 200)
        self.assertTrue(res_invite_ok.json()["delegate_id"].startswith("CLT-"))

        # Case E: GET /delegates/list with CLIENT role -> 403 Forbidden
        app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
            subject="client_viewer_1", role=PrincipalRole.CLIENT
        )
        res_list_fail = client.get("/api/v1/mobile/delegates/list")
        self.assertEqual(res_list_fail.status_code, 403)

        # Case F: GET /delegates/list with FOUNDER role -> 200 OK with masked passcodes
        app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
            subject="ajay_founder", role=PrincipalRole.FOUNDER
        )
        res_list_ok = client.get("/api/v1/mobile/delegates/list")
        self.assertEqual(res_list_ok.status_code, 200)
        delegates_data = res_list_ok.json()
        self.assertGreater(len(delegates_data), 0)
        for d in delegates_data:
            self.assertTrue(d["passcode"].endswith("****") or d["passcode"] == "******")

        # Clean up dependency overrides
        app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
