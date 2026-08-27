import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.models import (
    ApprovalRecord,
    AttemptRecord,
    AuditEventRecord,
    DeploymentRecord,
    GateEvidenceRecord,
    ProjectRecord,
    TaskRecord,
    WorkerHealthRecord,
    WorkerRecord,
)
from alpha_core.security import redact_secrets, worker_kill_switch
from alpha_protocol import (
    ApprovalStatus,
    GateEvidence,
    GateType,
    RiskClass,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    WorkerHealthReport,
    WorkerRegistration,
    compute_packet_digest,
    is_legal_transition,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive UTC values before Python-side comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def ensure_dict(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            res = json.loads(val)
            return res if isinstance(res, dict) else {}
        except Exception:
            return {}
    return {}


class TaskEngine:
    """Core state engine managing atomic task leasing, results, watchdog, and audit logging."""

    @staticmethod
    def _transition(task: TaskRecord, target_status: TaskStatus) -> None:
        """Apply only a protocol-defined task status transition."""
        current_status = TaskStatus(task.status)
        if not is_legal_transition(current_status, target_status):
            raise ValueError(
                f"Illegal task transition: {current_status.value} -> {target_status.value}"
            )
        task.status = target_status.value

    @staticmethod
    async def create_project(
        session: AsyncSession,
        project_id: str,
        name: str,
        repo_path: str,
    ) -> ProjectRecord:
        res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
        proj = res.scalar_one_or_none()
        if not proj:
            proj = ProjectRecord(
                id=project_id,
                name=name,
                repo_path=repo_path,
            )
            session.add(proj)
            await session.flush()

        return cast(ProjectRecord, proj)

    @staticmethod
    async def project_progress_snapshot(
        session: AsyncSession,
        project_id: str,
        recent_event_limit: int = 20,
    ) -> dict[str, Any] | None:
        """Return founder-safe progress state from task and audit system of record."""
        return await TaskEngine.generate_reporting_snapshot(
            session=session,
            project_id=project_id,
            viewer_role="founder",
            recent_event_limit=recent_event_limit,
        )

    @staticmethod
    async def generate_reporting_snapshot(
        session: AsyncSession,
        project_id: str,
        viewer_role: str = "client",
        recent_event_limit: int = 20,
    ) -> dict[str, Any] | None:
        """
        Generate comprehensive reporting snapshot for founder or client views:
        work completed, evidence summaries, preview status, blockers, elapsed time,
        uptime, downtime, and next owner action.
        """
        project = await session.get(ProjectRecord, project_id)
        if not project:
            return None

        task_result = await session.execute(
            select(TaskRecord).where(TaskRecord.project_id == project_id)
        )
        tasks = task_result.scalars().all()

        status_counts: dict[str, int] = {}
        for task in tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1

        active_statuses = {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}
        completed_statuses = {TaskStatus.VERIFIED.value, TaskStatus.COMPLETED.value}
        waiting_approval = status_counts.get(TaskStatus.WAITING_APPROVAL.value, 0)
        blocked = status_counts.get(TaskStatus.BLOCKED.value, 0)
        retrying = status_counts.get(TaskStatus.RETRYABLE_FAILED.value, 0)
        active = sum(status_counts.get(status, 0) for status in active_statuses)
        queued = status_counts.get(TaskStatus.QUEUED.value, 0)

        if waiting_approval:
            next_owner_action = "founder_approval_required"
        elif blocked:
            next_owner_action = "investigate_blocked_task"
        elif retrying:
            next_owner_action = "await_retry_backoff"
        elif active:
            next_owner_action = "worker_active"
        elif queued:
            next_owner_action = "await_worker_lease"
        else:
            next_owner_action = "no_open_tasks"

        # Deployments & Previews
        dep_result = await session.execute(
            select(DeploymentRecord)
            .where(DeploymentRecord.project_id == project_id)
            .order_by(DeploymentRecord.created_at.desc())
        )
        deployments = dep_result.scalars().all()
        previews = [
            {
                "deployment_id": d.id,
                "environment": d.target_environment,
                "status": d.status,
                "deploy_url": d.deploy_url,
                "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
            }
            for d in deployments
        ]

        # Audit Events
        events_result = await session.execute(
            select(AuditEventRecord)
            .where(AuditEventRecord.project_id == project_id)
            .order_by(AuditEventRecord.timestamp.desc())
            .limit(recent_event_limit)
        )
        events = events_result.scalars().all()

        # Task Attempt Durations and Costs
        task_ids = [t.id for t in tasks]
        total_duration = 0.0
        total_cost = 0.0
        total_tokens = 0
        if task_ids:
            attempt_result = await session.execute(
                select(AttemptRecord).where(AttemptRecord.task_id.in_(task_ids))
            )
            attempts = attempt_result.scalars().all()
            for att in attempts:
                total_duration += att.duration_seconds or 0.0
                total_cost += att.estimated_cost_usd or 0.0
                total_tokens += (att.input_tokens or 0) + (att.output_tokens or 0)

        # Worker uptime metrics
        workers_res = await session.execute(select(WorkerRecord))
        all_workers = workers_res.scalars().all()
        online_count = sum(1 for w in all_workers if w.status == "online")
        total_workers = len(all_workers)
        uptime_pct = (
            round((online_count / total_workers * 100.0), 1) if total_workers > 0 else 100.0
        )

        snapshot: dict[str, Any] = {
            "project_id": project.id,
            "project_name": project.name,
            "total_tasks": len(tasks),
            "completed_tasks": sum(status_counts.get(status, 0) for status in completed_statuses),
            "active_tasks": active,
            "queued_tasks": queued,
            "waiting_approval_tasks": waiting_approval,
            "retrying_tasks": retrying,
            "blocked_tasks": blocked,
            "status_counts": status_counts,
            "next_owner_action": next_owner_action,
            "previews": previews,
            "metrics": {
                "elapsed_time_seconds": round(total_duration, 2),
                "estimated_cost_usd": round(total_cost, 4),
                "total_tokens": total_tokens,
                "worker_uptime_percent": uptime_pct,
            },
            "recent_events": [
                {
                    "event_type": event.event_type,
                    "task_id": event.task_id,
                    "actor": event.actor if viewer_role == "founder" else "system",
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                }
                for event in events
            ],
        }
        return snapshot

    @staticmethod
    async def record_control_event(
        session: AsyncSession,
        event_type: str,
        project_id: str | None,
        task_id: str | None,
        details: dict[str, Any],
        actor: str = "system",
        checkpoint: dict[str, Any] | None = None,
    ) -> AuditEventRecord:
        """Records an append-only, scrubbed control plane progress/checkpoint event."""
        payload = dict(details)
        if checkpoint:
            payload["checkpoint"] = checkpoint

        cleaned_json = redact_secrets(json.dumps(payload, default=str))
        audit = AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            project_id=project_id,
            task_id=task_id,
            actor=actor,
            details_json=json.loads(cleaned_json),
            timestamp=utc_now(),
        )
        session.add(audit)
        await session.flush()
        return audit

    @staticmethod
    async def register_worker(
        session: AsyncSession,
        registration: WorkerRegistration,
    ) -> WorkerRecord:
        """Upsert authenticated worker identity and declared capabilities."""
        existing_worker = await session.get(WorkerRecord, registration.worker_id)
        if existing_worker:
            worker = existing_worker
            worker.hostname = registration.hostname
            worker.platform = registration.platform
            worker.capability_json = registration.capability.model_dump(mode="json")
            worker.status = "online"
        else:
            worker = WorkerRecord(
                id=registration.worker_id,
                hostname=registration.hostname,
                platform=registration.platform,
                capability_json=registration.capability.model_dump(mode="json"),
                status="online",
                registered_at=registration.registered_at,
            )
            session.add(worker)
        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="worker_registered",
                actor=registration.worker_id,
                details_json={
                    "platform": registration.platform,
                    "max_concurrent_tasks": registration.capability.max_concurrent_tasks,
                },
            )
        )
        await session.flush()
        return cast(WorkerRecord, worker)

    @staticmethod
    async def record_worker_health(
        session: AsyncSession,
        report: WorkerHealthReport,
    ) -> WorkerRecord | None:
        """Persist structured worker health sample and update worker liveness."""
        worker: WorkerRecord | None = await session.scalar(
            select(WorkerRecord).where(WorkerRecord.id == report.worker_id)
        )
        if worker:
            worker.last_heartbeat_at = report.reported_at
            worker.status = report.status.value

        health = WorkerHealthRecord(
            id=f"wh_{uuid.uuid4().hex[:12]}",
            worker_id=report.worker_id,
            battery_percent=report.battery_percent,
            ac_power=report.ac_power,
            thermal_pressure=report.thermal_pressure,
            cpu_load_percent=report.cpu_load_percent,
            disk_free_gb=report.disk_free_gb,
            active_task_count=report.active_task_count,
            reported_at=report.reported_at,
        )
        session.add(health)
        await session.flush()
        return worker

    @staticmethod
    async def record_heartbeat(
        session: AsyncSession,
        task_id_or_report: str | WorkerHealthReport,
        lease_token: str | None = None,
        worker_id: str | None = None,
        extend_seconds: int = 1800,
    ) -> bool:
        """Record either a task lease heartbeat or a worker health report."""
        if isinstance(task_id_or_report, WorkerHealthReport):
            await TaskEngine.record_worker_health(session, task_id_or_report)
            return True

        task_id = task_id_or_report
        query = select(TaskRecord).where(
            and_(
                TaskRecord.id == task_id,
                TaskRecord.lease_token == lease_token,
            )
        )
        if worker_id:
            query = query.where(TaskRecord.worker_id == worker_id)
        res = await session.execute(query)
        task = res.scalar_one_or_none()
        now = utc_now()
        if not TaskEngine._has_active_lease(task, lease_token or "", worker_id, now):
            return False

        if task:
            if task.status == TaskStatus.LEASED.value:
                TaskEngine._transition(task, TaskStatus.RUNNING)
            task.lease_expires_at = now + timedelta(seconds=extend_seconds)
            task.updated_at = now
            await session.flush()
            return True
        return False

    @staticmethod
    async def submit_task(
        session: AsyncSession,
        envelope: TaskEnvelope,
        project_id: str | None = None,
    ) -> TaskRecord:
        """Submit a task to the queue with dependency and approval checks."""
        dep_ids = [d.task_id for d in envelope.dependencies]
        if envelope.task_id in dep_ids:
            raise ValueError(f"Task '{envelope.task_id}' cannot depend on itself")

        effective_project_id = project_id or envelope.project_id
        await TaskEngine.create_project(
            session=session,
            project_id=effective_project_id,
            name=f"Project {effective_project_id}",
            repo_path=envelope.repo,
        )

        requires_approval = envelope.requires_approval or envelope.risk_class in {
            RiskClass.HIGH,
            RiskClass.CRITICAL,
        }
        initial_status = TaskStatus.WAITING_APPROVAL if requires_approval else TaskStatus.QUEUED

        task_data = envelope.model_dump(mode="json")
        packet_digest = compute_packet_digest(envelope)
        res = await session.execute(select(TaskRecord).where(TaskRecord.id == envelope.task_id))
        existing_task = res.scalar_one_or_none()

        if existing_task:
            if existing_task.status in {TaskStatus.VERIFIED.value, TaskStatus.COMPLETED.value}:
                if existing_task.details_json != task_data:
                    raise ValueError(
                        f"Cannot replace verified task '{envelope.task_id}' with modified definition"
                    )
                return cast(TaskRecord, existing_task)

            if existing_task.details_json == task_data:
                return cast(TaskRecord, existing_task)

            has_approval_res = await session.execute(
                select(ApprovalRecord).where(
                    and_(
                        ApprovalRecord.task_id == envelope.task_id,
                        ApprovalRecord.approval_type == "task_execution",
                    )
                )
            )
            if has_approval_res.first() is not None:
                raise ValueError(
                    "Cannot mutate task definition after execution approval is requested"
                )

            existing_task.repo = envelope.repo
            existing_task.base_commit = envelope.base_commit
            existing_task.objective = envelope.objective
            existing_task.details_json = task_data
            existing_task.packet_sha256 = packet_digest
            existing_task.risk_class = envelope.risk_class.value
            existing_task.preferred_agent = envelope.preferred_agent.value
            existing_task.depends_on_json = dep_ids
            existing_task.max_attempts = envelope.retry_policy.max_attempts
            existing_task.updated_at = utc_now()
            if existing_task.status != initial_status.value:
                existing_task.status = initial_status.value
            task = existing_task
        else:
            task = TaskRecord(
                id=envelope.task_id,
                project_id=effective_project_id,
                repo=envelope.repo,
                base_commit=envelope.base_commit,
                objective=envelope.objective,
                details_json=task_data,
                packet_sha256=packet_digest,
                risk_class=envelope.risk_class.value,
                preferred_agent=envelope.preferred_agent.value,
                status=initial_status.value,
                depends_on_json=dep_ids,
                max_attempts=envelope.retry_policy.max_attempts,
                created_at=envelope.created_at,
                updated_at=envelope.created_at,
            )
            session.add(task)

        if requires_approval:
            appr = ApprovalRecord(
                id=f"appr_{uuid.uuid4().hex[:12]}",
                task_id=envelope.task_id,
                approval_type="task_execution",
                scope_sha256=packet_digest,
                status=ApprovalStatus.PENDING.value,
                created_at=envelope.created_at,
            )
            session.add(appr)

        audit = AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            # Queue admission is recorded even when execution must wait for a
            # founder approval.  The status in details keeps that distinction
            # explicit for progress reports and recovery tooling.
            event_type="task_queued",
            project_id=effective_project_id,
            task_id=envelope.task_id,
            actor="client",
            details_json={
                "task": json.loads(redact_secrets(envelope.model_dump_json())),
                "initial_status": initial_status.value,
            },
        )
        session.add(audit)
        await session.flush()
        return cast(TaskRecord, task)

    @staticmethod
    async def cancel_task(
        session: AsyncSession,
        task_id: str,
        reason: str,
        actor: str = "founder",
    ) -> bool:
        """Transitions an eligible task to CANCELLED and releases any active lease."""
        task = await session.get(TaskRecord, task_id)
        if not task:
            return False
        active_assignment = task.status in {
            TaskStatus.LEASED.value,
            TaskStatus.RUNNING.value,
        }
        TaskEngine._transition(task, TaskStatus.CANCELLED)
        task.lease_expires_at = None
        if not active_assignment:
            task.lease_token = None
            task.worker_id = None
        task.updated_at = utc_now()

        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="task_cancelled",
                project_id=task.project_id,
                task_id=task.id,
                actor=actor,
                details_json={"reason": reason},
            )
        )
        await session.flush()
        return True

    @staticmethod
    async def block_task(
        session: AsyncSession,
        task_id: str,
        reason: str,
        actor: str = "system",
    ) -> bool:
        """Transitions a task to BLOCKED state and releases its lease."""
        task = await session.get(TaskRecord, task_id)
        if not task:
            return False
        TaskEngine._transition(task, TaskStatus.BLOCKED)
        task.lease_token = None
        task.lease_expires_at = None
        task.worker_id = None
        task.updated_at = utc_now()

        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="task_blocked",
                project_id=task.project_id,
                task_id=task.id,
                actor=actor,
                details_json={"reason": reason},
            )
        )
        await session.flush()
        return True

    @staticmethod
    async def supersede_task(
        session: AsyncSession,
        task_id: str,
        new_task_id: str,
        actor: str = "founder",
    ) -> bool:
        """Marks a verified task SUPERSEDED by a newer task iteration."""
        task = await session.get(TaskRecord, task_id)
        if not task:
            return False
        TaskEngine._transition(task, TaskStatus.SUPERSEDED)
        task.updated_at = utc_now()

        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="task_superseded",
                project_id=task.project_id,
                task_id=task.id,
                actor=actor,
                details_json={"new_task_id": new_task_id},
            )
        )
        await session.flush()
        return True

    @staticmethod
    async def decide_task_approval(
        session: AsyncSession,
        task_id: str,
        approved: bool,
        decided_by: str,
        reason: str | None = None,
        packet_sha256: str | None = None,
        review_sha256: str | None = None,
    ) -> TaskRecord | None:
        """Approve or reject a pending task approval."""
        res = await session.execute(
            select(ApprovalRecord)
            .where(
                and_(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.status == ApprovalStatus.PENDING.value,
                )
            )
            .order_by(ApprovalRecord.created_at.desc())
        )
        approval = res.scalar_one_or_none()
        if not approval:
            return None

        task: TaskRecord | None = await session.scalar(
            select(TaskRecord).where(TaskRecord.id == task_id)
        )
        if not task:
            return None

        envelope = TaskEnvelope.model_validate(task.details_json)

        if approval.approval_type == "task_review":
            if not review_sha256 or review_sha256 != approval.scope_sha256:
                raise ValueError("Founder review digest mismatch or missing")

            # Recompute digest from persisted task + attempt data
            from alpha_protocol import AgentType, compute_review_digest

            att_res = await session.execute(
                select(AttemptRecord)
                .where(AttemptRecord.task_id == task_id)
                .order_by(AttemptRecord.completed_at.desc())
                .limit(1)
            )
            attempt = att_res.scalar_one_or_none()
            if not attempt:
                raise ValueError("No attempt found for review")

            from alpha_protocol.gates import GateResult

            # construct TaskResult
            tr = TaskResult(
                attempt_id=attempt.id,
                task_id=attempt.task_id,
                status=TaskStatus(attempt.status),
                agent=AgentType(attempt.agent),
                model=attempt.model,
                base_commit=envelope.base_commit,
                result_commit=attempt.result_commit,
                packet_sha256=attempt.packet_sha256,
                files_changed=(
                    attempt.files_changed_json
                    if isinstance(attempt.files_changed_json, list)
                    else (
                        json.loads(attempt.files_changed_json) if attempt.files_changed_json else []
                    )
                ),
                gate_result=(
                    GateResult.model_validate(attempt.gate_result_json)
                    if isinstance(attempt.gate_result_json, dict)
                    else (
                        GateResult.model_validate_json(attempt.gate_result_json)
                        if attempt.gate_result_json
                        else None
                    )
                ),
            )
            recomputed = compute_review_digest(tr, attempt.worker_id or "")
            if review_sha256 != recomputed:
                raise ValueError("Founder review digest mismatch with recomputed state")

            now = utc_now()
            approval.status = (
                ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
            )
            approval.decided_by = decided_by
            approval.reason = reason
            approval.decided_at = now

            if approved:
                TaskEngine._transition(task, TaskStatus.COMPLETED)
            else:
                TaskEngine._transition(task, TaskStatus.BLOCKED)

            audit = AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="task_review_approved" if approved else "task_review_rejected",
                project_id=task.project_id,
                task_id=task.id,
                actor=decided_by,
                details_json={
                    "attempt_id": attempt.id,
                    "review_sha256": review_sha256,
                    "reason": reason,
                },
                timestamp=now,
            )
            session.add(audit)
            await session.flush()
            return task

        elif envelope.require_packet_binding:
            fresh_digest = compute_packet_digest(envelope)
            if (
                not packet_sha256
                or packet_sha256 != task.packet_sha256
                or packet_sha256 != approval.scope_sha256
                or packet_sha256 != fresh_digest
            ):
                raise ValueError("Task packet digest mismatch or missing")

        now = utc_now()
        approval.decided_by = decided_by
        approval.decided_at = now
        approval.reason = reason

        if approved:
            approval.status = ApprovalStatus.APPROVED.value
            TaskEngine._transition(task, TaskStatus.QUEUED)
            event_type = "task_approval_approved"
        else:
            approval.status = ApprovalStatus.REJECTED.value
            TaskEngine._transition(task, TaskStatus.CANCELLED)
            event_type = "task_approval_rejected"

        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type=event_type,
                project_id=task.project_id,
                task_id=task.id,
                actor=decided_by,
                details_json={"reason": reason or ""},
            )
        )
        await session.flush()
        return task

    @staticmethod
    async def decide_approval(
        session: AsyncSession,
        task_id: str,
        approved: bool,
        decided_by: str,
        reason: str | None = None,
    ) -> bool:
        """Approve or reject a pending task approval (returns bool)."""
        task = await TaskEngine.decide_task_approval(
            session=session,
            task_id=task_id,
            approved=approved,
            decided_by=decided_by,
            reason=reason,
        )
        return task is not None

    @staticmethod
    async def timeout_expired_leases(session: AsyncSession) -> int:
        """Finds abandoned leased/running tasks whose lease has expired and triggers backoff or escalation."""
        now = utc_now()
        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    TaskRecord.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                    TaskRecord.lease_expires_at.is_not(None),
                )
            )
        )
        tasks = res.scalars().all()
        expired = [
            t for t in tasks if t.lease_expires_at and normalize_utc(t.lease_expires_at) < now
        ]
        for task in expired:
            task.lease_token = None
            task.worker_id = None
            task.lease_expires_at = None
            task.attempt_count = task.attempt_count or 0
            if task.attempt_count >= task.max_attempts:
                TaskEngine._transition(task, TaskStatus.BLOCKED)
                task.next_eligible_at = None
            else:
                TaskEngine._transition(task, TaskStatus.RETRYABLE_FAILED)
                await TaskEngine._schedule_retry(session, task, now, actor="lease_timeout")
        if expired:
            await session.flush()
        return len(expired)

    @staticmethod
    async def release_due_retries(session: AsyncSession) -> int:
        """Releases retryable tasks whose backoff window has elapsed back into the queued pool."""
        now = utc_now()
        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    TaskRecord.status == TaskStatus.RETRYABLE_FAILED.value,
                    TaskRecord.next_eligible_at.is_not(None),
                )
            )
        )
        tasks = res.scalars().all()
        due = [t for t in tasks if t.next_eligible_at and normalize_utc(t.next_eligible_at) <= now]
        for task in due:
            TaskEngine._transition(task, TaskStatus.QUEUED)
            task.next_eligible_at = None
            task.lease_token = None
            task.worker_id = None
            task.lease_expires_at = None
            session.add(
                AuditEventRecord(
                    id=f"evt_{uuid.uuid4().hex[:12]}",
                    event_type="task_requeued_from_retry",
                    project_id=task.project_id,
                    task_id=task.id,
                    actor="system",
                )
            )
        if due:
            await session.flush()
        return len(due)

    @staticmethod
    async def lease_next_task(
        session: AsyncSession,
        worker_id: str,
        lease_duration_seconds: int = 300,
        preferred_agent: str | None = None,
    ) -> tuple[TaskRecord, TaskEnvelope] | None:
        """Atomic task leasing with dependencies, concurrency limits, and pause enforcement."""
        if not worker_kill_switch.can_execute():
            return None

        now = utc_now()
        await TaskEngine._recover_expired_leases(session, now)

        # Worker concurrency check
        worker_record = await session.get(WorkerRecord, worker_id)
        worker_cap = 1
        if worker_record and worker_record.capability_json:
            cap_dict = ensure_dict(worker_record.capability_json)
            worker_cap = cap_dict.get("max_concurrent_tasks", 1)

        active_worker_tasks_res = await session.execute(
            select(func.count(TaskRecord.id)).where(
                and_(
                    TaskRecord.worker_id == worker_id,
                    TaskRecord.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                )
            )
        )
        if (active_worker_tasks_res.scalar() or 0) >= worker_cap:
            return None

        query = (
            select(TaskRecord)
            .where(
                and_(
                    TaskRecord.status == TaskStatus.QUEUED.value,
                    or_(
                        TaskRecord.next_eligible_at.is_(None),
                        TaskRecord.next_eligible_at <= now,
                    ),
                )
            )
            .order_by(TaskRecord.created_at.asc())
        )

        if session.bind and session.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        res = await session.execute(query)
        candidates = res.scalars().all()

        for candidate in candidates:
            if preferred_agent and candidate.preferred_agent != preferred_agent:
                continue
            if not worker_kill_switch.can_execute(candidate.project_id):
                continue

            envelope = TaskEnvelope.model_validate(candidate.details_json)
            if envelope.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}:
                appr_res = await session.execute(
                    select(ApprovalRecord).where(
                        and_(
                            ApprovalRecord.task_id == candidate.id,
                            ApprovalRecord.status == ApprovalStatus.APPROVED.value,
                        )
                    )
                )
                if not appr_res.scalar_one_or_none():
                    continue

            # Project concurrency limits
            project_cap = envelope.concurrency_policy.max_per_project
            active_proj_res = await session.execute(
                select(func.count(TaskRecord.id)).where(
                    and_(
                        TaskRecord.project_id == candidate.project_id,
                        TaskRecord.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                    )
                )
            )
            if (active_proj_res.scalar() or 0) >= project_cap:
                continue

            # Dependency verification
            dep_task_ids = [d.task_id for d in envelope.dependencies]
            if dep_task_ids:
                dep_res = await session.execute(
                    select(TaskRecord.status).where(
                        and_(
                            TaskRecord.project_id == candidate.project_id,
                            TaskRecord.id.in_(dep_task_ids),
                        )
                    )
                )
                dep_statuses = dep_res.scalars().all()
                if len(dep_statuses) != len(dep_task_ids):
                    continue
                if not all(
                    s in {TaskStatus.VERIFIED.value, TaskStatus.COMPLETED.value}
                    for s in dep_statuses
                ):
                    continue

            if envelope.require_packet_binding:
                fresh_digest = compute_packet_digest(envelope)
                if candidate.packet_sha256 != fresh_digest:
                    TaskEngine._transition(candidate, TaskStatus.BLOCKED)
                    session.add(
                        AuditEventRecord(
                            id=f"evt_{uuid.uuid4().hex[:12]}",
                            event_type="task_blocked_digest_mismatch",
                            project_id=candidate.project_id,
                            task_id=candidate.id,
                            actor="system",
                            details_json={
                                "reason": "Stored task packet digest mismatch before lease"
                            },
                        )
                    )
                    await session.flush()
                    continue

            lease_token = f"lease_{uuid.uuid4().hex}"
            TaskEngine._transition(candidate, TaskStatus.LEASED)
            candidate.lease_token = lease_token
            candidate.leased_at = now
            candidate.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
            candidate.next_eligible_at = None
            candidate.worker_id = worker_id
            candidate.attempt_count += 1

            session.add(
                AuditEventRecord(
                    id=f"evt_{uuid.uuid4().hex[:12]}",
                    event_type="task_leased",
                    project_id=candidate.project_id,
                    task_id=candidate.id,
                    actor=worker_id,
                    details_json={"lease_token": lease_token, "worker_id": worker_id},
                )
            )
            await session.flush()
            return candidate, envelope

        return None

    @staticmethod
    async def check_watchdog_stalls(
        session: AsyncSession,
        stall_timeout_seconds: int = 300,
    ) -> list[str]:
        """
        Task-progress heartbeat watchdog:
        Identifies active leased/running tasks whose execution has stalled without bounded progress,
        releases them safely, and triggers backoff retry or escalation.
        """
        now = utc_now()
        threshold = now - timedelta(seconds=stall_timeout_seconds)

        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    TaskRecord.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                    TaskRecord.leased_at.is_not(None),
                )
            )
        )
        all_active = res.scalars().all()
        stalled_tasks = [
            task
            for task in all_active
            if task.leased_at and normalize_utc(task.leased_at) < threshold
        ]
        stalled_ids: list[str] = []

        for task in stalled_tasks:
            worker_id = task.worker_id or "unknown"
            task.lease_token = None
            task.lease_expires_at = None
            task.worker_id = None

            if task.attempt_count >= task.max_attempts:
                TaskEngine._transition(task, TaskStatus.BLOCKED)
                task.next_eligible_at = None
                event_type = "task_stalled_escalated"
            else:
                TaskEngine._transition(task, TaskStatus.RETRYABLE_FAILED)
                await TaskEngine._schedule_retry(session, task, now, actor="watchdog")
                event_type = "task_stalled_retrying"

            session.add(
                AuditEventRecord(
                    id=f"evt_{uuid.uuid4().hex[:12]}",
                    event_type=event_type,
                    project_id=task.project_id,
                    task_id=task.id,
                    actor="watchdog",
                    details_json={
                        "stalled_worker_id": worker_id,
                        "stall_timeout_seconds": stall_timeout_seconds,
                    },
                )
            )
            stalled_ids.append(task.id)

        await session.flush()
        return stalled_ids

    @staticmethod
    async def resume_checkpointed_task(
        session: AsyncSession,
        task_id: str,
        checkpoint: dict[str, Any],
    ) -> bool:
        """
        Idempotent wake/recovery worker logic:
        Resumes a checkpointed task validating matching project, repository, worktree,
        lease token, and side-effect state.
        """
        task = await session.get(TaskRecord, task_id)
        if not task:
            return False

        if task.project_id != checkpoint.get("project_id"):
            return False

        if task.lease_token and checkpoint.get("lease_token") != task.lease_token:
            return False

        if task.status == TaskStatus.LEASED.value:
            TaskEngine._transition(task, TaskStatus.RUNNING)

        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="task_resumed_from_checkpoint",
                project_id=task.project_id,
                task_id=task.id,
                actor=checkpoint.get("worker_id", "worker"),
                details_json=checkpoint,
            )
        )
        await session.flush()
        return True

    @staticmethod
    async def submit_result(
        session: AsyncSession,
        result: TaskResult,
        lease_token: str,
        worker_id: str | None = None,
    ) -> bool:
        """Submit task execution result with strict gate validation and independent review rules."""
        # Check duplicate idempotent submission
        dup_res = await session.execute(
            select(AttemptRecord).where(AttemptRecord.id == result.attempt_id)
        )
        existing_attempt = dup_res.scalar_one_or_none()
        if existing_attempt:
            if worker_id and existing_attempt.worker_id and existing_attempt.worker_id != worker_id:
                return False
            return bool(
                existing_attempt.task_id == result.task_id
                and existing_attempt.status == result.status.value
                and existing_attempt.result_commit == result.result_commit
            )

        query = select(TaskRecord).where(
            and_(
                TaskRecord.id == result.task_id,
                TaskRecord.lease_token == lease_token,
            )
        )
        if worker_id:
            query = query.where(TaskRecord.worker_id == worker_id)
        res = await session.execute(query)
        task = res.scalar_one_or_none()
        now = utc_now()
        if not TaskEngine._has_active_lease(task, lease_token, worker_id, now):
            return False

        envelope = TaskEnvelope.model_validate(task.details_json)

        if envelope.require_packet_binding:
            fresh_digest = compute_packet_digest(envelope)
            if (
                not result.packet_sha256
                or result.packet_sha256 != task.packet_sha256
                or result.packet_sha256 != fresh_digest
                or result.base_commit != envelope.base_commit
            ):
                return False

        if result.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
            if not result.gate_result or not result.gate_result.evidence_items:
                print("DEBUG: missing evidence")
                return False
            if result.gate_result.task_id != result.task_id:
                print("DEBUG: task_id mismatch")
                return False
            if result.gate_result.attempt_id != result.attempt_id:
                print("DEBUG: attempt_id mismatch")
                return False

            ev_ids = [ev.evidence_id for ev in result.gate_result.evidence_items]
            if len(ev_ids) != len(set(ev_ids)):
                print("DEBUG: duplicate ev_ids")
                return False

            evidence_by_gate: dict[GateType, list[GateEvidence]] = {}
            for ev in result.gate_result.evidence_items:
                evidence_by_gate.setdefault(ev.gate_type, []).append(ev)

            for req_gate in envelope.acceptance_plan.required_gates:
                gate_evs = evidence_by_gate.get(req_gate, [])
                if not gate_evs:
                    print(f"DEBUG: missing required gate {req_gate}")
                    return False
                if any(not ev.passed for ev in gate_evs):
                    print("DEBUG: failed required gate")
                    return False

            if envelope.acceptance_plan.commands:
                for cmd in envelope.acceptance_plan.commands:
                    expected_argv = [cmd.executable, *cmd.args]
                    gate_evs = evidence_by_gate.get(cmd.gate_type, [])
                    found_match = False
                    for ev in gate_evs:
                        if not ev.passed:
                            continue
                        metrics = ev.metrics or {}
                        if (
                            metrics.get("command_argv") == expected_argv
                            and metrics.get("exit_code") == 0
                        ):
                            found_match = True
                            break
                    if not found_match:
                        print(
                            f"DEBUG: expected_argv not matched. expected={expected_argv} found_metrics={[ev.metrics for ev in gate_evs]}"
                        )
                        return False

            if result.files_changed:
                if not result.result_commit:
                    print("DEBUG: files changed but no result commit")
                    return False
                from pathlib import PurePosixPath

                allowed_paths = envelope.allowed_paths
                for raw_path in result.files_changed:
                    path = PurePosixPath(raw_path)
                    if path.is_absolute() or ".." in path.parts:
                        print("DEBUG: absolute or .. in path")
                        return False

                    if "." not in allowed_paths:
                        matched = False
                        for ap in allowed_paths:
                            try:
                                path.relative_to(PurePosixPath(ap))
                                matched = True
                                break
                            except ValueError:
                                pass
                            if path == PurePosixPath(ap):
                                matched = True
                                break
                        if not matched:
                            print(f"DEBUG: not in allowed path {raw_path}")
                            return False

        if task.status == TaskStatus.LEASED.value:
            TaskEngine._transition(task, TaskStatus.RUNNING)

        # Evaluate acceptance gates and required gate evidence
        if result.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
            gates_passed = True
            target_status = TaskStatus.VERIFIED

            # 1. Validate gate result and explicit command evidence
            if not result.gate_result or not result.gate_result.all_passed:
                gates_passed = False
            else:
                evidence_types = {
                    ev.gate_type: ev for ev in result.gate_result.evidence_items if ev.passed
                }
                if envelope.acceptance_plan.commands:
                    for cmd in envelope.acceptance_plan.commands:
                        if cmd.gate_type not in evidence_types:
                            gates_passed = False
                            break

            # 2. Enforce independent review for high/critical risks
            if envelope.acceptance_plan.require_independent_review or envelope.risk_class in {
                RiskClass.HIGH,
                RiskClass.CRITICAL,
            }:
                has_independent_review = False
                if result.gate_result:
                    for ev in result.gate_result.evidence_items:
                        if ev.gate_type == GateType.INDEPENDENT_REVIEW and ev.passed:
                            reviewer = ev.metrics.get("reviewer") or ev.summary
                            if reviewer and reviewer != (worker_id or task.worker_id):
                                has_independent_review = True
                                break
                if not has_independent_review:
                    # Require founder review approval before completion
                    target_status = TaskStatus.WAITING_APPROVAL
                    gates_passed = False

            if not gates_passed and target_status != TaskStatus.WAITING_APPROVAL:
                target_status = TaskStatus.RETRYABLE_FAILED
        elif result.status in {
            TaskStatus.RETRYABLE_FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.CANCELLED,
        }:
            target_status = result.status
        else:
            return False

        if not is_legal_transition(TaskStatus(task.status), target_status):
            return False

        # Record attempt
        attempt = AttemptRecord(
            id=result.attempt_id,
            task_id=result.task_id,
            worker_id=worker_id,
            agent=result.agent.value,
            model=result.model,
            status=result.status.value,
            result_commit=result.result_commit,
            packet_sha256=result.packet_sha256,
            files_changed_json=result.files_changed,
            gate_result_json=result.gate_result.model_dump(mode="json")
            if result.gate_result
            else None,
            completed_at=now,
        )
        session.add(attempt)

        if result.gate_result and result.gate_result.evidence_items:
            for ev in result.gate_result.evidence_items:
                evidence_rec = GateEvidenceRecord(
                    id=f"ev_{base64.urlsafe_b64encode(hashlib.sha256(f'{result.attempt_id}_{ev.evidence_id}'.encode()).digest()).decode().rstrip('=')}",
                    task_id=result.task_id,
                    attempt_id=result.attempt_id,
                    gate_type=ev.gate_type.value,
                    passed=ev.passed,
                    summary=ev.summary,
                    output_log=ev.output_log,
                    metrics_json=ev.metrics,
                    created_at=ev.timestamp,
                )
                session.add(evidence_rec)

        TaskEngine._transition(task, target_status)
        task.lease_token = None
        task.lease_expires_at = None
        task.worker_id = None
        if target_status == TaskStatus.RETRYABLE_FAILED:
            await TaskEngine._schedule_retry(session, task, now, actor=result.agent.value)

        audit = AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="result_submitted",
            project_id=task.project_id,
            task_id=task.id,
            actor=result.agent.value,
            details_json=json.loads(redact_secrets(result.model_dump_json())),
        )
        session.add(audit)

        if target_status == TaskStatus.VERIFIED and envelope.require_packet_binding:
            from alpha_protocol import compute_review_digest

            review_digest = compute_review_digest(result, worker_id or "")
            appr = ApprovalRecord(
                id=f"appr_{uuid.uuid4().hex[:12]}",
                task_id=result.task_id,
                approval_type="task_review",
                scope_sha256=review_digest,
                status=ApprovalStatus.PENDING.value,
                created_at=now,
            )
            session.add(appr)

            review_audit = AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type="task_review_pending",
                project_id=task.project_id,
                task_id=task.id,
                actor="system",
                details_json={"attempt_id": result.attempt_id, "review_sha256": review_digest},
                timestamp=now,
            )
            session.add(review_audit)

        await session.flush()
        return True

    @staticmethod
    def _has_active_lease(
        task: TaskRecord | None,
        lease_token: str,
        worker_id: str | None,
        now: datetime,
    ) -> bool:
        if task is None:
            return False
        if not task.lease_token or task.lease_token != lease_token:
            return False
        if worker_id is not None and task.worker_id and task.worker_id != worker_id:
            return False
        if task.status not in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}:
            return False
        if task.lease_expires_at is None:
            return False
        return normalize_utc(task.lease_expires_at) >= now

    @staticmethod
    async def _schedule_retry(
        session: AsyncSession,
        task: TaskRecord,
        now: datetime,
        actor: str,
    ) -> None:
        """Schedule bounded exponential retry without immediate retry loops."""
        envelope = TaskEnvelope.model_validate(task.details_json)
        if task.attempt_count >= task.max_attempts:
            TaskEngine._transition(task, TaskStatus.BLOCKED)
            task.next_eligible_at = None
            event_type = "task_retry_exhausted"
            details = {"attempt_count": task.attempt_count, "max_attempts": task.max_attempts}
        else:
            policy = envelope.retry_policy
            delay_seconds = min(
                policy.backoff_base_seconds * policy.backoff_multiplier ** (task.attempt_count - 1),
                policy.deadline_seconds,
            )
            task.next_eligible_at = now + timedelta(seconds=delay_seconds)
            event_type = "task_retry_scheduled"
            details = {
                "attempt_count": task.attempt_count,
                "retry_after_seconds": delay_seconds,
                "next_eligible_at": task.next_eligible_at.isoformat(),
            }

        session.add(
            AuditEventRecord(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type=event_type,
                project_id=task.project_id,
                task_id=task.id,
                actor=actor,
                details_json=details,
            )
        )

    @staticmethod
    async def _recover_expired_leases(session: AsyncSession, now: datetime) -> None:
        """Requeue expired leases with retry backoff."""
        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    TaskRecord.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                    TaskRecord.lease_expires_at.is_not(None),
                    TaskRecord.lease_expires_at < now,
                )
            )
        )
        expired_tasks = res.scalars().all()
        for task in expired_tasks:
            prev_worker = task.worker_id or "unknown"
            task.lease_token = None
            task.lease_expires_at = None
            task.worker_id = None
            TaskEngine._transition(task, TaskStatus.RETRYABLE_FAILED)
            await TaskEngine._schedule_retry(session, task, now, actor="system_recovery")

            session.add(
                AuditEventRecord(
                    id=f"evt_{uuid.uuid4().hex[:12]}",
                    event_type="lease_expired_requeued",
                    project_id=task.project_id,
                    task_id=task.id,
                    actor="system",
                    details_json={"expired_worker_id": prev_worker},
                )
            )
