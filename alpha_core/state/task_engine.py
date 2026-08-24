import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.models import (
    AttemptRecord,
    AuditEventRecord,
    ProjectRecord,
    TaskRecord,
)
from alpha_protocol import (
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskEngine:
    """Core state engine managing atomic task leasing, results, and audit logging."""

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
        return proj

    @staticmethod
    async def submit_task(
        session: AsyncSession,
        envelope: TaskEnvelope,
    ) -> TaskRecord:
        # Check if project exists, or create a stub project
        res_p = await session.execute(select(ProjectRecord).where(ProjectRecord.id == envelope.project_id))
        proj = res_p.scalar_one_or_none()
        if not proj:
            proj = ProjectRecord(
                id=envelope.project_id,
                name=f"Project {envelope.project_id}",
                repo_path=envelope.repo,
            )
            session.add(proj)
            await session.flush()

        # Idempotent task creation / update
        res_t = await session.execute(select(TaskRecord).where(TaskRecord.id == envelope.task_id))
        task = res_t.scalar_one_or_none()

        if task:
            task.repo = envelope.repo
            task.base_commit = envelope.base_commit
            task.objective = envelope.objective
            task.details_json = envelope.model_dump_json()
            task.risk_class = envelope.risk_class.value
            task.preferred_agent = envelope.preferred_agent.value
            task.status = TaskStatus.QUEUED.value
            task.lease_token = None
            task.lease_expires_at = None
        else:
            task = TaskRecord(
                id=envelope.task_id,
                project_id=envelope.project_id,
                repo=envelope.repo,
                base_commit=envelope.base_commit,
                objective=envelope.objective,
                details_json=envelope.model_dump_json(),
                risk_class=envelope.risk_class.value,
                preferred_agent=envelope.preferred_agent.value,
                status=TaskStatus.QUEUED.value,
            )
            session.add(task)

        # Audit event
        audit = AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="task_queued",
            project_id=envelope.project_id,
            task_id=envelope.task_id,
            actor="system",
            details_json=envelope.model_dump_json(),
        )
        session.add(audit)
        await session.flush()
        return task

    @staticmethod
    async def lease_next_task(
        session: AsyncSession,
        worker_id: str,
        preferred_agent: str | None = None,
    ) -> tuple[TaskRecord, TaskEnvelope] | None:
        """Atomically leases the next available queued task."""
        query = select(TaskRecord).where(TaskRecord.status == TaskStatus.QUEUED.value)
        if preferred_agent:
            query = query.where(TaskRecord.preferred_agent == preferred_agent)
        query = query.order_by(TaskRecord.created_at.asc()).limit(1)

        res = await session.execute(query)
        task = res.scalar_one_or_none()
        if not task:
            return None

        lease_token = f"lease_{uuid.uuid4().hex}"
        now = utc_now()
        envelope = TaskEnvelope.model_validate_json(task.details_json)
        timeout_delta = timedelta(seconds=envelope.lease_timeout_seconds)

        task.status = TaskStatus.LEASED.value
        task.worker_id = worker_id
        task.lease_token = lease_token
        task.leased_at = now
        task.lease_expires_at = now + timeout_delta

        audit = AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="task_leased",
            project_id=task.project_id,
            task_id=task.id,
            actor=worker_id,
            details_json=f'{{"lease_token": "{lease_token}", "worker_id": "{worker_id}"}}',
        )
        session.add(audit)
        await session.flush()
        return task, envelope

    @staticmethod
    async def record_heartbeat(
        session: AsyncSession,
        task_id: str,
        lease_token: str,
        extend_seconds: int = 1800,
    ) -> bool:
        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    TaskRecord.id == task_id,
                    TaskRecord.lease_token == lease_token,
                )
            )
        )
        task = res.scalar_one_or_none()
        if not task:
            return False

        task.lease_expires_at = utc_now() + timedelta(seconds=extend_seconds)
        await session.flush()
        return True

    @staticmethod
    async def submit_result(
        session: AsyncSession,
        result: TaskResult,
        lease_token: str,
    ) -> bool:
        """Processes task result from worker and marks status based on gate evidence."""
        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    TaskRecord.id == result.task_id,
                    TaskRecord.lease_token == lease_token,
                )
            )
        )
        task = res.scalar_one_or_none()
        if not task:
            return False

        # Record attempt
        attempt = AttemptRecord(
            id=result.attempt_id,
            task_id=result.task_id,
            agent=result.agent.value,
            model=result.model,
            status=result.status.value,
            result_commit=result.result_commit,
            files_changed_json=str(result.files_changed),
            gate_result_json=result.gate_result.model_dump_json() if result.gate_result else None,
            completed_at=utc_now(),
        )
        session.add(attempt)

        # Decide final task status based on gate evidence
        if result.status == TaskStatus.COMPLETED or result.status == TaskStatus.VERIFIED:
            if result.gate_result and result.gate_result.all_passed:
                task.status = TaskStatus.VERIFIED.value
            else:
                task.status = TaskStatus.RETRYABLE_FAILED.value
        else:
            task.status = result.status.value

        task.lease_token = None
        task.lease_expires_at = None

        audit = AuditEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type="result_submitted",
            project_id=task.project_id,
            task_id=task.id,
            actor=result.agent.value,
            details_json=result.model_dump_json(),
        )
        session.add(audit)
        await session.flush()
        return True

    @staticmethod
    async def timeout_expired_leases(session: AsyncSession) -> int:
        """Finds abandoned leased tasks and safely requeues them."""
        now = utc_now()
        res = await session.execute(
            select(TaskRecord).where(
                and_(
                    or_(
                        TaskRecord.status == TaskStatus.LEASED.value,
                        TaskRecord.status == TaskStatus.RUNNING.value,
                    ),
                    TaskRecord.lease_expires_at < now,
                )
            )
        )
        expired_tasks = res.scalars().all()
        for task in expired_tasks:
            task.status = TaskStatus.QUEUED.value
            task.lease_token = None
            task.lease_expires_at = None
            session.add(
                AuditEventRecord(
                    id=f"evt_{uuid.uuid4().hex[:12]}",
                    event_type="lease_timeout_requeued",
                    project_id=task.project_id,
                    task_id=task.id,
                    actor="system",
                    details_json=f'{{"expired_at": "{now.isoformat()}"}}',
                )
            )
        await session.flush()
        return len(expired_tasks)
