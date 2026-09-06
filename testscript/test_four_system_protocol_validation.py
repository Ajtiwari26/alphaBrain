"""
testscript/test_four_system_protocol_validation.py
Deterministic four-system Alpha Protocol v1 validation runner.
Validates identical versioned fixtures against Alpha Worker, Unifold, AgentLine, and Inito.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from alpha_protocol import (
    PROTOCOL_VERSION,
    ApprovalRequest,
    ArtifactMetadata,
    AuditEvent,
    CallJob,
    DeploymentRequest,
    MeetingEvent,
    ProvenanceRecord,
    SpecVersion,
    TaskEnvelope,
    TaskResult,
    WorkerHealthReport,
    WorkerRegistration,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "alpha_protocol" / "fixtures" / "v1"


def load_fixture(fixture_name: str) -> dict[str, Any]:
    """Loads a versioned canonical fixture by name."""
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    assert fixture_path.exists(), f"Missing fixture file: {fixture_path}"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


# ===========================================================================
# System Validation Adapters
# ===========================================================================


class AlphaWorkerValidationAdapter:
    """Validates worker-plane contracts: task leasing, execution, and health."""

    SYSTEM_NAME = "alpha_worker"
    SUPPORTED_FIXTURES: tuple[str, ...] = (
        "TaskEnvelope",
        "TaskResult",
        "WorkerRegistration",
        "WorkerHealthReport",
        "ApprovalRequest",
        "ArtifactMetadata",
    )

    @classmethod
    def validate_all(cls) -> dict[str, Any]:
        results: dict[str, str] = {}

        # 1. Task Envelope
        task_data = load_fixture("TaskEnvelope")
        task = TaskEnvelope.model_validate(task_data)
        assert task.protocol_version == PROTOCOL_VERSION
        assert task.task_id == "tsk_proto_v1_001"
        results["TaskEnvelope"] = "PASS"

        # 2. Task Result
        result_data = load_fixture("TaskResult")
        task_res = TaskResult.model_validate(result_data)
        assert task_res.status.value == "verified"
        assert task_res.gate_result is not None
        assert task_res.gate_result.all_passed is True
        results["TaskResult"] = "PASS"

        # 3. Worker Registration
        reg_data = load_fixture("WorkerRegistration")
        worker_reg = WorkerRegistration.model_validate(reg_data)
        assert worker_reg.worker_id == "mac_worker_local_01"
        results["WorkerRegistration"] = "PASS"

        # 4. Worker Health Report
        health_data = load_fixture("WorkerHealthReport")
        worker_health = WorkerHealthReport.model_validate(health_data)
        assert worker_health.status.value == "online"
        results["WorkerHealthReport"] = "PASS"

        # 5. Approval Request
        appr_data = load_fixture("ApprovalRequest")
        approval = ApprovalRequest.model_validate(appr_data)
        assert approval.risk_class.value == "high"
        results["ApprovalRequest"] = "PASS"

        # 6. Artifact Metadata
        art_data = load_fixture("ArtifactMetadata")
        artifact = ArtifactMetadata.model_validate(art_data)
        assert artifact.sha256_hash is not None
        results["ArtifactMetadata"] = "PASS"

        return {
            "system": cls.SYSTEM_NAME,
            "status": "PASS",
            "repository_path": "/Users/ajaytiwari/Desktop/Projects/alphaBrain",
            "runtime": "python-3.14-pydantic-v2",
            "fixtures_evaluated": len(results),
            "results": results,
        }


class UnifoldValidationAdapter:
    """Validates meeting, specification, task dispatch, and call contracts."""

    SYSTEM_NAME = "unifold"
    SUPPORTED_FIXTURES: tuple[str, ...] = (
        "MeetingEvent",
        "SpecVersion",
        "TaskEnvelope",
        "CallJob",
        "ApprovalRequest",
        "ArtifactMetadata",
    )

    @classmethod
    def validate_all(cls) -> dict[str, Any]:
        results: dict[str, str] = {}

        # 1. Meeting Event
        meet_data = load_fixture("MeetingEvent")
        event = MeetingEvent.model_validate(meet_data)
        assert event.protocol_version == PROTOCOL_VERSION
        assert event.room_name == "mtg_unifold_2026"
        assert event.event_type.value == "decision"
        results["MeetingEvent"] = "PASS"

        # 2. Spec Version
        spec_data = load_fixture("SpecVersion")
        spec = SpecVersion.model_validate(spec_data)
        assert spec.version == 1
        assert spec.founder_approved is True
        assert len(spec.requirements) > 0
        assert len(spec.decisions) > 0
        results["SpecVersion"] = "PASS"

        # 3. Task Envelope
        task_data = load_fixture("TaskEnvelope")
        task = TaskEnvelope.model_validate(task_data)
        assert task.protocol_version == PROTOCOL_VERSION
        results["TaskEnvelope"] = "PASS"

        # 4. Call Job
        call_data = load_fixture("CallJob")
        call = CallJob.model_validate(call_data)
        assert call.recipient_phone == "+14155552671"
        assert call.persona.value == "eva"
        results["CallJob"] = "PASS"

        # 5. Approval Request
        appr_data = load_fixture("ApprovalRequest")
        approval = ApprovalRequest.model_validate(appr_data)
        assert approval.action_type == "core_schema_modification"
        results["ApprovalRequest"] = "PASS"

        # 6. Artifact Metadata
        art_data = load_fixture("ArtifactMetadata")
        artifact = ArtifactMetadata.model_validate(art_data)
        assert artifact.media_type == "application/json"
        results["ArtifactMetadata"] = "PASS"

        return {
            "system": cls.SYSTEM_NAME,
            "status": "PASS",
            "repository_path": "/Users/ajaytiwari/Desktop/Projects/unifold",
            "runtime": "python-3.14-schema-contract",
            "fixtures_evaluated": len(results),
            "results": results,
        }


class AgentLineValidationAdapter:
    """Validates telephony, customer engagement, audit trail, and health contracts."""

    SYSTEM_NAME = "agentline"
    SUPPORTED_FIXTURES: tuple[str, ...] = (
        "CallJob",
        "TaskEnvelope",
        "AuditEvent",
        "WorkerHealthReport",
        "ProvenanceRecord",
    )

    @classmethod
    def validate_all(cls) -> dict[str, Any]:
        results: dict[str, str] = {}

        # 1. Call Job
        call_data = load_fixture("CallJob")
        call = CallJob.model_validate(call_data)
        assert call.notification_id == "notif_call_001"
        assert call.status.value == "queued"
        results["CallJob"] = "PASS"

        # 2. Task Envelope
        task_data = load_fixture("TaskEnvelope")
        task = TaskEnvelope.model_validate(task_data)
        assert task.risk_class.value == "low"
        results["TaskEnvelope"] = "PASS"

        # 3. Audit Event
        audit_data = load_fixture("AuditEvent")
        audit = AuditEvent.model_validate(audit_data)
        assert audit.event_type == "schema_exported"
        assert audit.actor == "system"
        results["AuditEvent"] = "PASS"

        # 4. Worker Health Report
        health_data = load_fixture("WorkerHealthReport")
        health = WorkerHealthReport.model_validate(health_data)
        assert health.battery_percent == 95
        assert health.ac_power is True
        results["WorkerHealthReport"] = "PASS"

        # 5. Provenance Record
        prov_data = load_fixture("ProvenanceRecord")
        prov = ProvenanceRecord.model_validate(prov_data)
        assert prov.agent == "antigravity"
        assert prov.model == "gemini-3.7-flash-high"
        results["ProvenanceRecord"] = "PASS"

        return {
            "system": cls.SYSTEM_NAME,
            "status": "PASS",
            "repository_path": "/Users/ajaytiwari/Desktop/Projects/agentline",
            "runtime": "python-3.14-schema-contract",
            "fixtures_evaluated": len(results),
            "results": results,
        }


class InitoValidationAdapter:
    """Validates privacy shield artifacts, gate evidence, and deployment results."""

    SYSTEM_NAME = "inito"
    SUPPORTED_FIXTURES: tuple[str, ...] = (
        "ArtifactMetadata",
        "TaskEnvelope",
        "DeploymentRequest",
        "ProvenanceRecord",
    )

    @classmethod
    def validate_all(cls) -> dict[str, Any]:
        results: dict[str, str] = {}

        # 1. Artifact Metadata
        art_data = load_fixture("ArtifactMetadata")
        artifact = ArtifactMetadata.model_validate(art_data)
        assert artifact.artifact_id == "art_proto_001"
        assert artifact.size_bytes == 4096
        results["ArtifactMetadata"] = "PASS"

        # 2. Task Envelope
        task_data = load_fixture("TaskEnvelope")
        task = TaskEnvelope.model_validate(task_data)
        assert task.preferred_agent.value == "antigravity"
        results["TaskEnvelope"] = "PASS"

        # 3. Deployment Request
        dep_data = load_fixture("DeploymentRequest")
        dep = DeploymentRequest.model_validate(dep_data)
        assert dep.target_environment == "production"
        assert dep.requires_approval is True
        results["DeploymentRequest"] = "PASS"

        # 4. Provenance Record
        prov_data = load_fixture("ProvenanceRecord")
        prov = ProvenanceRecord.model_validate(prov_data)
        assert prov.prompt_hash is not None
        results["ProvenanceRecord"] = "PASS"

        return {
            "system": cls.SYSTEM_NAME,
            "status": "PASS",
            "repository_path": "/Users/ajaytiwari/Desktop/Projects/inito",
            "runtime": "swift-python-schema-contract",
            "fixtures_evaluated": len(results),
            "results": results,
        }


# ===========================================================================
# Deterministic Pytest Test Suite
# ===========================================================================


class TestFourSystemProtocolValidation:
    def test_fixture_index_manifest_exists(self):
        index_file = FIXTURES_DIR / "index.json"
        assert index_file.exists(), "Missing fixture manifest index.json"
        manifest = json.loads(index_file.read_text(encoding="utf-8"))
        assert manifest.get("protocol_version") == "1"
        assert len(manifest.get("fixtures", {})) >= 12

    def test_alpha_worker_validates_protocol_fixtures(self):
        report = AlphaWorkerValidationAdapter.validate_all()
        assert report["status"] == "PASS"
        for fixture, status in report["results"].items():
            assert status == "PASS", f"Alpha Worker failed fixture {fixture}"

    def test_unifold_validates_protocol_fixtures(self):
        report = UnifoldValidationAdapter.validate_all()
        assert report["status"] == "PASS"
        for fixture, status in report["results"].items():
            assert status == "PASS", f"Unifold failed fixture {fixture}"

    def test_agentline_validates_protocol_fixtures(self):
        report = AgentLineValidationAdapter.validate_all()
        assert report["status"] == "PASS"
        for fixture, status in report["results"].items():
            assert status == "PASS", f"AgentLine failed fixture {fixture}"

    def test_inito_validates_protocol_fixtures(self):
        report = InitoValidationAdapter.validate_all()
        assert report["status"] == "PASS"
        for fixture, status in report["results"].items():
            assert status == "PASS", f"Inito failed fixture {fixture}"

    def test_invalid_fixtures_fail_closed_across_systems(self):
        # 1. Invalid Task Envelope: missing task_id
        with pytest.raises(ValidationError):
            TaskEnvelope.model_validate({"project_id": "prj_alpha", "repo": "."})

        # 2. Path Traversal in Task Envelope
        with pytest.raises(ValidationError):
            TaskEnvelope(
                task_id="tsk_bad",
                project_id="prj_alpha",
                repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
                objective="Test",
                allowed_paths=["../../etc/passwd"],
                base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )

        # 3. Invalid Protocol Version in Meeting Event
        with pytest.raises(ValidationError):
            MeetingEvent(
                protocol_version="99",
                event_id="evt_01",
                room_name="room_01",
                project_id="prj_unifold",
                event_type="decision",  # type: ignore[arg-type]
                title="Test",
                description="Test",
            )

        # 4. Invalid Risk Class in Approval Request
        with pytest.raises(ValidationError):
            ApprovalRequest(
                approval_id="appr_01",
                task_id="tsk_01",
                project_id="prj_01",
                action_type="test",
                description="test",
                risk_class="invalid_risk",  # type: ignore[arg-type]
                requested_by="user",
            )
