"""
testscript/test_agy_daemon_policy.py
Deterministic unit tests for AlphaWorkerDaemon policy evaluation, ActionBroker
integration, and attempt outcome to TaskStatus state mapping.
"""

from alpha_protocol import (
    AcceptancePlan,
    GateCommand,
    GateType,
    RiskClass,
    TaskEnvelope,
    TaskStatus,
)
from alpha_worker.adapters.antigravity_live import (
    SDLC_SKILL_NAME,
    AGYAttemptStatus,
    AntigravityAttemptOutcome,
)
from alpha_worker.daemon import evaluate_daemon_task_lifecycle


def make_test_task(
    task_id: str = "tsk_policy_01",
    project_id: str = "prj_policy",
    requires_approval: bool = False,
    risk_class: RiskClass = RiskClass.LOW,
    repo: str = "/tmp/repo",
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        project_id=project_id,
        repo=repo,
        objective="Run safe policy test",
        detailed_instructions="Execute bounded unit task.",
        allowed_paths=["."],
        requires_approval=requires_approval,
        risk_class=risk_class,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["-q"],
                )
            ],
        ),
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )


def test_blocked_approval_prevents_execution():
    task = make_test_task(requires_approval=True)
    decision = evaluate_daemon_task_lifecycle(task, human_approval_granted=False)

    assert decision.should_execute is False
    assert decision.next_task_status in {TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED}
    assert "ActionBroker blocked execution" in decision.reason
    assert decision.action_decision is not None
    assert decision.action_decision.requires_human_approval is True


def test_critical_risk_requires_approval_prevents_execution():
    task = make_test_task(risk_class=RiskClass.CRITICAL, requires_approval=True)
    decision = evaluate_daemon_task_lifecycle(task, human_approval_granted=False)

    assert decision.should_execute is False
    assert decision.next_task_status in {TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED}
    assert decision.action_decision is not None
    assert decision.action_decision.requires_human_approval is True


def test_destructive_command_in_task_blocked():
    task = make_test_task()
    task.objective = "rm -rf /"
    decision = evaluate_daemon_task_lifecycle(task, human_approval_granted=False)

    assert decision.should_execute is False
    assert decision.next_task_status in {TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED}


def test_pre_execution_allowed_proceeds_to_running():
    task = make_test_task(requires_approval=False)
    decision = evaluate_daemon_task_lifecycle(task, human_approval_granted=True, approver="founder")

    assert decision.should_execute is True
    assert decision.next_task_status == TaskStatus.RUNNING
    assert "execution permitted" in decision.reason.lower()


def test_nonzero_or_failed_outcome_maps_to_retryable_failed():
    task = make_test_task()
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        exit_code=1,
        status=AGYAttemptStatus.FAILED,
        blocked_reason="Process exited with code 1",
    )
    decision = evaluate_daemon_task_lifecycle(task, attempt_outcome=outcome)

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.RETRYABLE_FAILED
    assert decision.next_task_status != TaskStatus.VERIFIED
    assert decision.next_task_status != TaskStatus.COMPLETED


def test_timeout_outcome_maps_to_retryable_failed():
    task = make_test_task()
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        exit_code=-1,
        status=AGYAttemptStatus.TIMED_OUT,
        blocked_reason="Execution timed out",
    )
    decision = evaluate_daemon_task_lifecycle(task, attempt_outcome=outcome)

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.RETRYABLE_FAILED
    assert decision.next_task_status != TaskStatus.VERIFIED


def test_cancelled_outcome_maps_to_cancelled():
    task = make_test_task()
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        status=AGYAttemptStatus.CANCELLED,
        blocked_reason="User cancelled execution",
    )
    decision = evaluate_daemon_task_lifecycle(task, attempt_outcome=outcome)

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.CANCELLED


def test_rate_limited_outcome_maps_to_retryable_failed():
    task = make_test_task()
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        status=AGYAttemptStatus.RATE_LIMITED,
        blocked_reason="API Quota exhausted",
    )
    decision = evaluate_daemon_task_lifecycle(task, attempt_outcome=outcome)

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.RETRYABLE_FAILED


def test_blocked_outcome_maps_to_blocked():
    task = make_test_task()
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        status=AGYAttemptStatus.BLOCKED,
        blocked_reason="Missing integration token",
    )
    decision = evaluate_daemon_task_lifecycle(task, attempt_outcome=outcome)

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.BLOCKED


def test_succeeded_without_gate_evidence_refuses_verified():
    task = make_test_task()
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        exit_code=0,
        status=AGYAttemptStatus.SUCCEEDED,
        gate_evidence=None,
        qa_evidence=None,
    )
    decision = evaluate_daemon_task_lifecycle(
        task, attempt_outcome=outcome, has_valid_gate_evidence=False
    )

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.RETRYABLE_FAILED
    assert decision.next_task_status != TaskStatus.VERIFIED
    assert decision.next_task_status != TaskStatus.COMPLETED
    assert "missing or invalid" in decision.reason.lower()


def test_succeeded_with_valid_gate_evidence_leads_only_to_verifying():
    task = make_test_task()
    qa_manifest = {
        "skill": SDLC_SKILL_NAME,
        "project_id": "prj_policy",
        "testscript_root": "testscript",
        "passed_gates": ["unit_test"],
        "security_review": {"executed": True, "status": "passed"},
    }
    outcome = AntigravityAttemptOutcome(
        conversation_id="conv-1",
        model="gemini-3.1-pro",
        exit_code=0,
        status=AGYAttemptStatus.SUCCEEDED,
        gate_evidence=qa_manifest,
        qa_evidence=qa_manifest,
        changed_files=("src/main.py",),
        diff_summary="1 file changed",
    )
    decision = evaluate_daemon_task_lifecycle(
        task, attempt_outcome=outcome, has_valid_gate_evidence=True
    )

    assert decision.should_execute is False
    assert decision.next_task_status == TaskStatus.VERIFIED
    assert decision.next_task_status != TaskStatus.COMPLETED
    assert decision.gate_evidence_valid is True
    assert "ready for verification gate" in decision.reason.lower()
