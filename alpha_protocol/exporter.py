import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    ArtifactMetadata,
    AuditEvent,
    CallJob,
    CallStatus,
    ConcurrencyPolicy,
    Decision,
    DeploymentRequest,
    DeploymentResult,
    GateCommand,
    GateEvidence,
    GateResult,
    GateType,
    MeetingEvent,
    MeetingEventType,
    MeetingSession,
    PersonaType,
    ProvenanceRecord,
    Requirement,
    RetryPolicy,
    RiskClass,
    RollbackRequest,
    SpecDocument,
    SpecVersion,
    TaskAttempt,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    TranscriptSegment,
    UsageRecord,
    WorkerCapability,
    WorkerHealth,
    WorkerHealthReport,
    WorkerRegistration,
)

PROTOCOL_MODELS: dict[str, type[BaseModel]] = {
    "TaskEnvelope": TaskEnvelope,
    "TaskResult": TaskResult,
    "TaskAttempt": TaskAttempt,
    "ApprovalRequest": ApprovalRequest,
    "ApprovalResult": ApprovalResult,
    "WorkerRegistration": WorkerRegistration,
    "WorkerHealthReport": WorkerHealthReport,
    "MeetingEvent": MeetingEvent,
    "MeetingSession": MeetingSession,
    "TranscriptSegment": TranscriptSegment,
    "SpecVersion": SpecVersion,
    "SpecDocument": SpecDocument,
    "Decision": Decision,
    "Requirement": Requirement,
    "CallJob": CallJob,
    "DeploymentRequest": DeploymentRequest,
    "DeploymentResult": DeploymentResult,
    "RollbackRequest": RollbackRequest,
    "ArtifactMetadata": ArtifactMetadata,
    "AuditEvent": AuditEvent,
    "ProvenanceRecord": ProvenanceRecord,
}


def build_sample_fixtures() -> dict[str, Any]:
    """Generates canonical sample fixtures for all protocol models."""
    sample_task = TaskEnvelope(
        task_id="tsk_proto_v1_001",
        project_id="prj_alpha",
        org_id="org_deploymate",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        base_commit="main",
        objective="Implement cross-project protocol validation",
        allowed_paths=["alpha_protocol", "testscript"],
        allowed_tools=["view_file", "edit_file", "run_command"],
        risk_class=RiskClass.LOW,
        preferred_agent=AgentType.ANTIGRAVITY,
        retry_policy=RetryPolicy(max_attempts=3, backoff_base_seconds=60),
        concurrency_policy=ConcurrencyPolicy(max_per_project=5, max_per_worker=2),
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.LINT],
            commands=[
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["testscript/test_protocol_v1.py"],
                ),
                GateCommand(
                    gate_type=GateType.LINT,
                    executable="ruff",
                    args=["check", "."],
                ),
            ],
        ),
    )

    sample_task_result = TaskResult(
        attempt_id="att_proto_v1_001",
        task_id="tsk_proto_v1_001",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-3.7-flash-high",
        base_commit="main",
        result_commit="a1b2c3d4e5f6",
        files_changed=["alpha_protocol/exporter.py"],
        gate_result=GateResult(
            task_id="tsk_proto_v1_001",
            attempt_id="att_proto_v1_001",
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id="evi_unit_001",
                    gate_type=GateType.UNIT_TEST,
                    passed=True,
                    summary="All protocol tests passed",
                    output_log="181 passed in 3.4s",
                )
            ],
        ),
        usage=UsageRecord(
            input_tokens=1500,
            output_tokens=400,
            duration_seconds=12.5,
            estimated_cost_usd=0.005,
            model="gemini-3.7-flash-high",
            provider="google",
        ),
    )

    sample_worker_reg = WorkerRegistration(
        worker_id="mac_worker_local_01",
        hostname="ajay-macbook-pro.local",
        platform="macos-arm64",
        capability=WorkerCapability(
            supported_agents=[AgentType.ANTIGRAVITY],
            supported_languages=["python", "typescript", "swift"],
            max_concurrent_tasks=2,
            has_gpu=False,
            has_display=True,
            platform="macos-arm64",
        ),
    )

    sample_worker_health = WorkerHealthReport(
        worker_id="mac_worker_local_01",
        status=WorkerHealth.ONLINE,
        battery_percent=95,
        ac_power=True,
        thermal_pressure="nominal",
        cpu_load_percent=14.2,
        disk_free_gb=120.5,
    )

    sample_meeting_event = MeetingEvent(
        event_id="evt_meet_001",
        room_name="mtg_unifold_2026",
        project_id="prj_unifold",
        event_type=MeetingEventType.DECISION,
        title="Approve Alpha Protocol v1",
        description="Agreed to standardize contracts across Unifold, AgentLine, Inito, and Alpha Worker.",
        speaker_identity="ajay",
        is_inference=False,
        confidence=1.0,
        tags=["architecture", "protocol", "v1"],
    )

    sample_call_job = CallJob(
        notification_id="notif_call_001",
        project_id="prj_agentline",
        recipient_phone="+14155552671",
        persona=PersonaType.EVA,
        purpose="Follow up on client intake and schedule demo",
        idempotency_key="idem_call_001",
        status=CallStatus.QUEUED,
    )

    sample_deployment = DeploymentRequest(
        deployment_id="dep_req_001",
        project_id="prj_alpha",
        task_id="tsk_proto_v1_001",
        attempt_id="att_proto_v1_001",
        target_environment="production",
        source_commit="commit_abc123",
        gate_evidence_ids=["evi_unit_001"],
        requires_approval=True,
        requested_by="operator-ajay",
    )

    sample_spec = SpecVersion(
        version=1,
        project_id="prj_alpha",
        title="Alpha Protocol Data Contracts",
        summary="Unified shared schemas for DeployMate ecosystem.",
        status=ApprovalStatus.APPROVED,
        founder_approved=True,
        client_approved=True,
        requirements=[
            Requirement(
                req_id="REQ-001",
                title="Strict Schema Validation",
                description="All external messages must validate against Alpha Protocol v1 models.",
            )
        ],
        decisions=[
            Decision(
                dec_id="DEC-001",
                topic="Protocol Versioning",
                decision="Freeze Protocol v1",
                rationale="Enables independent development across four client repositories.",
            )
        ],
    )

    sample_artifact = ArtifactMetadata(
        artifact_id="art_proto_001",
        project_id="prj_alpha",
        media_type="application/json",
        filename="protocol_v1_fixtures.json",
        size_bytes=4096,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_path="artifacts/prj_alpha/protocol_v1_fixtures.json",
        created_by="system",
        tags=["fixture", "v1", "schema"],
    )

    sample_approval = ApprovalRequest(
        approval_id="appr_001",
        task_id="tsk_proto_v1_001",
        project_id="prj_alpha",
        action_type="core_schema_modification",
        description="Modifying core schema models and exported protocol contracts",
        risk_class=RiskClass.HIGH,
        requested_by="worker-mac-01",
    )

    sample_audit = AuditEvent(
        event_id="audit_evt_001",
        event_type="schema_exported",
        project_id="prj_alpha",
        actor="system",
        details={"version": "1", "models_count": len(PROTOCOL_MODELS)},
    )

    sample_provenance = ProvenanceRecord(
        agent="antigravity",
        model="gemini-3.7-flash-high",
        prompt_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        tools_used=["view_file", "edit_file"],
        input_commit="a1b2c3d4e5f6",
    )

    return {
        "TaskEnvelope": sample_task,
        "TaskResult": sample_task_result,
        "WorkerRegistration": sample_worker_reg,
        "WorkerHealthReport": sample_worker_health,
        "MeetingEvent": sample_meeting_event,
        "CallJob": sample_call_job,
        "DeploymentRequest": sample_deployment,
        "SpecVersion": sample_spec,
        "ArtifactMetadata": sample_artifact,
        "ApprovalRequest": sample_approval,
        "AuditEvent": sample_audit,
        "ProvenanceRecord": sample_provenance,
    }


def export_all(base_dir: Path | None = None) -> dict[str, int]:
    """Exports schemas and sample fixtures to directory."""
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent

    schemas_dir = base_dir / "schemas" / "v1"
    fixtures_dir = base_dir / "fixtures" / "v1"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export JSON Schemas
    schema_count = 0
    for name, model_cls in PROTOCOL_MODELS.items():
        schema = model_cls.model_json_schema()
        schema_file = schemas_dir / f"{name}.json"
        schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        schema_count += 1

    # 2. Export canonical fixtures
    fixtures = build_sample_fixtures()
    fixture_count = 0
    manifest: dict[str, str] = {}
    for name, instance in fixtures.items():
        fixture_file = fixtures_dir / f"{name}.json"
        data = instance.model_dump(mode="json")
        fixture_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        manifest[name] = f"{name}.json"
        fixture_count += 1

    # Write manifest index
    (fixtures_dir / "index.json").write_text(
        json.dumps({"protocol_version": "1", "fixtures": manifest}, indent=2),
        encoding="utf-8",
    )

    return {"schemas": schema_count, "fixtures": fixture_count}


if __name__ == "__main__":
    result = export_all()
    print(f"Exported {result['schemas']} schemas and {result['fixtures']} fixtures.")
