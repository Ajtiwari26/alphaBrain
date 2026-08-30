"""Durable specification lifecycle and bounded task-graph drafting."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import cast

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.models import (
    ApprovalRecord,
    AuditEventRecord,
    ProjectRecord,
    SpecVersionRecord,
)
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    ApprovalStatus,
    RiskClass,
    SpecVersion,
    TaskEnvelope,
    compute_packet_digest,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def compute_spec_digest(spec: SpecVersion) -> str:
    """Hash immutable submitted specification content in canonical JSON form."""
    canonical = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TaskGraphPlanningConstraints(BaseModel):
    """Founder-controlled boundaries used to draft, but never submit, tasks."""

    base_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    allowed_paths: list[str] = Field(min_length=1, max_length=16)
    acceptance_plan: AcceptancePlan

    @field_validator("allowed_paths")
    @classmethod
    def reject_broad_or_testless_scope(cls, paths: list[str]) -> list[str]:
        if len(paths) != len(set(paths)):
            raise ValueError("Task-graph planning paths must be unique")
        if "." in paths:
            raise ValueError("Task-graph planning requires bounded paths; '.' is not allowed")
        if "testscript" not in paths:
            raise ValueError("Task-graph planning must allow the testscript directory")
        for raw_path in paths:
            if len(raw_path) > 256:
                raise ValueError("Task-graph planning paths must not exceed 256 characters")
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("Task-graph planning paths must be safe relative paths")
        return paths

    @field_validator("acceptance_plan")
    @classmethod
    def require_executable_evidence(cls, plan: AcceptancePlan) -> AcceptancePlan:
        if not plan.required_gates:
            raise ValueError("Task-graph planning requires at least one acceptance gate")
        if not plan.commands:
            raise ValueError("Task-graph planning requires typed gate commands")
        command_gates = {command.gate_type for command in plan.commands}
        missing_commands = set(plan.required_gates) - command_gates
        if missing_commands:
            names = ", ".join(sorted(gate.value for gate in missing_commands))
            raise ValueError(f"Task-graph planning gates lack typed commands: {names}")
        return plan


class TaskGraphDraft(BaseModel):
    """Non-executable task graph draft bound to one approved spec digest."""

    project_id: str
    spec_id: str
    spec_sha256: str
    graph_sha256: str
    task_packet_sha256: dict[str, str]
    tasks: list[TaskEnvelope]


class SpecEngine:
    """Own immutable spec submission, founder approval, and safe graph drafting."""

    MAX_REQUIREMENTS = 20

    @staticmethod
    def _record_id(project_id: str, version: int) -> str:
        identity = hashlib.sha256(f"{project_id}:{version}".encode()).hexdigest()[:24]
        return f"spc_{identity}"

    @staticmethod
    def _validate_draft(spec: SpecVersion) -> None:
        if not SAFE_ID.fullmatch(spec.project_id):
            raise ValueError("Specification project ID is invalid")
        if spec.version < 1:
            raise ValueError("Specification version must be positive")
        if not spec.title.strip() or len(spec.title) > 255:
            raise ValueError("Specification title must contain 1 to 255 characters")
        if not spec.summary.strip():
            raise ValueError("Specification summary is required")
        serialized_size = len(spec.model_dump_json().encode())
        if serialized_size > 262_144:
            raise ValueError("Specification exceeds 256 KiB size limit")
        if spec.status != ApprovalStatus.PENDING:
            raise ValueError("Submitted specification status must be pending")
        if spec.founder_approved or spec.client_approved or spec.approved_at is not None:
            raise ValueError("Submitted specification cannot contain approval claims")
        if not spec.requirements:
            raise ValueError("Specification requires at least one requirement")
        if len(spec.requirements) > SpecEngine.MAX_REQUIREMENTS:
            raise ValueError(
                f"Specification exceeds {SpecEngine.MAX_REQUIREMENTS} requirement planning limit"
            )
        identifier_groups = {
            "requirement": [item.req_id for item in spec.requirements],
            "decision": [item.dec_id for item in spec.decisions],
            "open question": [item.question_id for item in spec.open_questions],
        }
        for label, identifiers in identifier_groups.items():
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"Specification contains duplicate {label} IDs")

    @staticmethod
    def _spec_from_record(record: SpecVersionRecord) -> SpecVersion:
        frozen_spec = SpecEngine._frozen_spec_from_record(record)
        data = frozen_spec.model_dump(mode="json")
        data.update(
            {
                "status": record.status,
                "founder_approved": bool(record.founder_approved),
                "client_approved": bool(record.client_approved),
                "approved_at": record.approved_at,
            }
        )
        return cast(SpecVersion, SpecVersion.model_validate(data))

    @staticmethod
    def _frozen_spec_from_record(record: SpecVersionRecord) -> SpecVersion:
        raw_spec = record.spec_json
        if isinstance(raw_spec, str):
            raw_spec = json.loads(raw_spec)
        return cast(SpecVersion, SpecVersion.model_validate(dict(raw_spec)))

    @staticmethod
    async def submit_spec(
        session: AsyncSession,
        spec: SpecVersion,
        *,
        actor: str,
    ) -> tuple[SpecVersionRecord, str]:
        """Persist an immutable pending version with digest-bound founder approval."""
        SpecEngine._validate_draft(spec)
        project = await session.get(ProjectRecord, spec.project_id)
        if project is None:
            raise ValueError("Project must be registered before specification submission")

        spec_id = SpecEngine._record_id(spec.project_id, spec.version)
        frozen_data = spec.model_dump(mode="json")
        digest = compute_spec_digest(spec)
        existing = await session.get(SpecVersionRecord, spec_id)
        if existing is not None:
            if existing.spec_json != frozen_data:
                raise ValueError("Specification version already exists with different content")
            return existing, digest

        latest_version = (
            await session.execute(
                select(func.max(SpecVersionRecord.version)).where(
                    SpecVersionRecord.project_id == spec.project_id
                )
            )
        ).scalar_one_or_none()
        expected_version = (latest_version or 0) + 1
        if spec.version != expected_version:
            raise ValueError(f"Specification version must be {expected_version}")

        record = SpecVersionRecord(
            id=spec_id,
            project_id=spec.project_id,
            version=spec.version,
            title=spec.title,
            summary=spec.summary,
            spec_json=frozen_data,
            status=ApprovalStatus.PENDING.value,
            founder_approved=False,
            client_approved=False,
            created_at=spec.created_at,
        )
        session.add(record)
        await session.flush()
        session.add(
            ApprovalRecord(
                id=f"appr_{uuid.uuid4().hex[:12]}",
                spec_id=spec_id,
                approval_type="spec_approval",
                scope_sha256=digest,
                status=ApprovalStatus.PENDING.value,
                created_at=spec.created_at,
            )
        )
        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="spec_submitted",
                project_id=spec.project_id,
                actor=actor,
                details_json={
                    "spec_id": spec_id,
                    "version": spec.version,
                    "scope_sha256": digest,
                },
            )
        )
        await session.flush()
        return record, digest

    @staticmethod
    async def decide_founder_approval(
        session: AsyncSession,
        spec_id: str,
        *,
        approved: bool,
        actor: str,
        scope_sha256: str,
        reason: str | None = None,
    ) -> SpecVersionRecord:
        """Bind founder decision to exact immutable specification digest."""
        record = await session.get(SpecVersionRecord, spec_id)
        if record is None:
            raise ValueError("Specification not found")
        approval = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.spec_id == spec_id,
                    ApprovalRecord.approval_type == "spec_approval",
                )
            )
        ).scalar_one_or_none()
        if approval is None:
            raise ValueError("Specification approval record is missing")
        current_digest = compute_spec_digest(SpecEngine._frozen_spec_from_record(record))
        if (
            not approval.scope_sha256
            or approval.scope_sha256 != current_digest
            or scope_sha256 != current_digest
        ):
            raise ValueError("Specification approval digest mismatch")
        if approval.status != ApprovalStatus.PENDING.value:
            if approved and approval.status == ApprovalStatus.APPROVED.value:
                return cast(SpecVersionRecord, record)
            raise ValueError("Specification approval has already been decided")

        now = utc_now()
        decision = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        approval.status = decision.value
        approval.decided_by = actor
        approval.reason = reason
        approval.decided_at = now
        record.status = decision.value
        record.founder_approved = approved
        record.approved_at = now if approved else None
        if approved:
            project = await session.get(ProjectRecord, record.project_id)
            if project is None:
                raise ValueError("Specification project no longer exists")
            project.active_spec_version = record.version
        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="spec_approved" if approved else "spec_rejected",
                project_id=record.project_id,
                actor=actor,
                details_json={
                    "spec_id": spec_id,
                    "version": record.version,
                    "scope_sha256": scope_sha256,
                    "reason": reason,
                },
            )
        )
        await session.flush()
        return cast(SpecVersionRecord, record)

    @staticmethod
    async def draft_task_graph(
        session: AsyncSession,
        spec_id: str,
        constraints: TaskGraphPlanningConstraints,
    ) -> TaskGraphDraft:
        """Create deterministic non-executable tasks from one founder-approved spec."""
        record = await session.get(SpecVersionRecord, spec_id)
        if record is None:
            raise ValueError("Specification not found")
        if record.status != ApprovalStatus.APPROVED.value or not record.founder_approved:
            raise ValueError("Specification requires founder approval before task planning")
        spec = SpecEngine._spec_from_record(record)
        unresolved = [
            question.question_id for question in spec.open_questions if not question.resolved
        ]
        if unresolved:
            raise ValueError(
                "Specification has unresolved open questions: " + ", ".join(sorted(unresolved))
            )

        frozen_spec = SpecEngine._frozen_spec_from_record(record)
        spec_digest = compute_spec_digest(frozen_spec)
        approval = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.spec_id == spec_id,
                    ApprovalRecord.approval_type == "spec_approval",
                    ApprovalRecord.status == ApprovalStatus.APPROVED.value,
                )
            )
        ).scalar_one_or_none()
        if approval is None or approval.scope_sha256 != spec_digest:
            raise ValueError("Approved specification digest no longer matches frozen content")
        key = hashlib.sha256(f"{spec_id}:{spec_digest}".encode()).hexdigest()[:12]
        source = f"spec:{spec_id}:{spec_digest}"
        project = await session.get(ProjectRecord, record.project_id)
        if project is None:
            raise ValueError("Specification project no longer exists")

        requirement_sections: list[str] = []
        for requirement in spec.requirements:
            criteria = "\n".join(f"  - {item}" for item in requirement.acceptance_criteria)
            requirement_sections.append(
                f"- {requirement.req_id} — {requirement.title}\n"
                f"  Description: {requirement.description}\n"
                f"  Acceptance criteria:\n{criteria or '  - No additional criteria supplied'}"
            )
        instructions = (
            "Implement and verify every requirement from the exact approved specification below.\n\n"
            + "\n".join(requirement_sections)
            + "\n\nStay within allowed paths. Put every test helper or fixture under testscript/. "
            "Run all typed acceptance commands. Stop and report rather than expanding scope."
        )
        delivery_task = TaskEnvelope(
            task_id=f"tsk_{key}_delivery",
            project_id=record.project_id,
            repo=project.repo_path,
            base_commit=constraints.base_commit,
            objective="Implement and verify exact approved specification",
            detailed_instructions=instructions,
            inputs=[source],
            allowed_paths=constraints.allowed_paths,
            risk_class=RiskClass.MEDIUM,
            acceptance_plan=constraints.acceptance_plan.model_copy(
                update={"require_independent_review": True}
            ),
            preferred_agent=AgentType.ANTIGRAVITY,
            requires_approval=True,
            require_packet_binding=True,
            created_at=spec.created_at,
        )
        tasks = [delivery_task]

        graph_data = [task.model_dump(mode="json") for task in tasks]
        graph_digest = hashlib.sha256(
            json.dumps(graph_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return TaskGraphDraft(
            project_id=record.project_id,
            spec_id=spec_id,
            spec_sha256=spec_digest,
            graph_sha256=graph_digest,
            task_packet_sha256={task.task_id: compute_packet_digest(task) for task in tasks},
            tasks=tasks,
        )
