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

from alpha_core.mobile_bridge.schemas import (  # noqa: E402
    AdminFeedbackVerdictRequest,
    DelegateAuthRequest,
    DelegateInviteRequest,
    FeedbackCreateRequest,
)
from alpha_core.mobile_bridge.service import MobileBridgeService  # noqa: E402
from alpha_core.queue.triage_queue import DEFAULT_DB_PATH, TaskTriageQueue  # noqa: E402


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
        updated = self.service.admin_verdict_on_feedback(item.id, verdict)
        self.assertEqual(updated.status, "handed_over")
        self.assertIsNotNone(updated.admitted_task_id)

        # 3. Verify task exists in SQLite triage queue!
        tasks = self.queue.list_tasks(limit=10)
        found_task = next((t for t in tasks if str(t.get("id")) == updated.admitted_task_id), None)
        self.assertIsNotNone(found_task)
        self.assertIn("Critical: Add p99 latency SLA check", str(found_task.get("title") or found_task.get("envelope_json")))


if __name__ == "__main__":
    unittest.main()
