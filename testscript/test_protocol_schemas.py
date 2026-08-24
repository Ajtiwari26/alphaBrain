"""
testscript/test_protocol_schemas.py
Automated unit tests for alpha_protocol Pydantic models and serialization.
"""

from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    AuditEvent,
    CallJob,
    CallStatus,
    Decision,
    GateCommand,
    GateEvidence,
    GateResult,
    GateType,
    PersonaType,
    Requirement,
    RiskClass,
    SpecVersion,
    TaskEnvelope,
)


def test_task_envelope_serialization():
    task = TaskEnvelope(
        task_id="tsk_test_101",
        project_id="prj_alpha",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Implement authentication middleware",
        allowed_paths=["alpha_core/auth.py", "testscript/test_auth.py"],
        allowed_tools=["edit_file", "run_command", "view_file"],
        risk_class=RiskClass.MEDIUM,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.LINT, GateType.UNIT_TEST],
            commands=[
                GateCommand(
                    gate_type=GateType.LINT,
                    executable="ruff",
                    args=["check", "alpha_core/auth.py"],
                ),
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["testscript/test_auth.py"],
                ),
            ],
        ),
        preferred_agent=AgentType.ANTIGRAVITY,
    )

    data = task.model_dump()
    assert data["task_id"] == "tsk_test_101"
    assert data["risk_class"] == "medium"
    assert data["preferred_agent"] == "antigravity"

    # Test roundtrip JSON conversion
    json_str = task.model_dump_json()
    reloaded = TaskEnvelope.model_validate_json(json_str)
    assert reloaded.task_id == task.task_id
    assert len(reloaded.acceptance_plan.required_gates) == 2


def test_gate_result_and_evidence():
    evidence = GateEvidence(
        evidence_id="evi_01",
        gate_type=GateType.UNIT_TEST,
        passed=True,
        summary="61 unit tests passed in 1.4s",
        metrics={"passed": 61, "failed": 0, "duration": 1.4},
    )

    result = GateResult(
        task_id="tsk_test_101",
        attempt_id="att_test_101_1",
        all_passed=True,
        evidence_items=[evidence],
    )

    assert result.all_passed is True
    assert len(result.evidence_items) == 1
    assert result.evidence_items[0].metrics["passed"] == 61


def test_spec_version_lifecycle():
    req = Requirement(
        req_id="req_01",
        title="Duplex Voice Streaming",
        raw_quote="We need the agent to respond with zero delay during the phone call",
        description="Stream raw PCM audio chunks over Plivo WebSocket directly to Gemini Live",
        acceptance_criteria=["Barge-in interrupts playback within 200ms"],
    )

    dec = Decision(
        dec_id="dec_01",
        topic="Audio Engine",
        decision="Use unified Gemini Live bidirectional audio manager",
        rationale="Prevents duplicate code between LiveKit and Plivo telephony",
    )

    spec = SpecVersion(
        version=1,
        project_id="prj_alpha",
        title="Alpha Brain Voice Architecture",
        summary="Specifications for real-time voice and telephony",
        requirements=[req],
        decisions=[dec],
    )

    assert spec.version == 1
    assert spec.founder_approved is False
    assert len(spec.requirements) == 1
    assert spec.requirements[0].req_id == "req_01"


def test_call_job_contract():
    job = CallJob(
        notification_id="ntf_call_101",
        persona=PersonaType.EVA,
        recipient_phone="+1234567890",
        recipient_name="Ajay Tiwari",
        purpose="founder_preview_review",
        script_facts={"preview_url": "http://localhost:3000", "gates_passed": 5},
        idempotency_key="idemp_101_attempt_1",
    )

    assert job.status == CallStatus.QUEUED
    assert job.persona == PersonaType.EVA
    assert job.script_facts["gates_passed"] == 5


def test_audit_event():
    event = AuditEvent(
        event_id="evt_001",
        event_type="task_leased",
        project_id="prj_alpha",
        task_id="tsk_test_101",
        actor="alpha_worker",
        details={"worker_host": "macbook_air", "worktree": "/tmp/alpha-worktrees/tsk_test_101"},
    )

    assert event.actor == "alpha_worker"
    assert event.details["worker_host"] == "macbook_air"
