import asyncio
import subprocess
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.db.models import (
    ApprovalRecord,
    AttemptRecord,
    AuditEventRecord,
    Base,
    TaskRecord,
)
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AgentType,
    GateEvidence,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    compute_packet_digest,
)

# Check for Docker before running
try:
    subprocess.check_output(["docker", "info"], stderr=subprocess.STDOUT, timeout=5.0)
    DOCKER_AVAILABLE = True
except Exception:
    DOCKER_AVAILABLE = False


@pytest.fixture(scope="session")
def postgres_url():
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is required for real PostgreSQL concurrency proofs")

    container_name = f"alphabrain_pg_test_{uuid.uuid4().hex[:8]}"
    subprocess.check_call(
        [
            "docker",
            "run",
            "--name",
            container_name,
            "-e",
            "POSTGRES_USER=test_user",
            "-e",
            "POSTGRES_PASSWORD=test_pass",
            "-e",
            "POSTGRES_DB=test_db",
            "-p",
            "127.0.0.1::5432",
            "-d",
            "postgres:17",
        ],
        timeout=15.0,
    )

    try:
        import time

        port_out = (
            subprocess.check_output(["docker", "port", container_name, "5432/tcp"], timeout=5.0)
            .decode()
            .strip()
        )
        first_line = port_out.split("\n")[0]
        host_port = first_line.rsplit(":", 1)[1]

        sync_url = f"postgresql+psycopg://test_user:test_pass@localhost:{host_port}/test_db"
        async_url = f"postgresql+psycopg://test_user:test_pass@localhost:{host_port}/test_db"

        # Wait for DB to be ready
        import sqlalchemy as sync_sa

        sync_engine = sync_sa.create_engine(sync_url)
        for _ in range(30):
            try:
                with sync_engine.begin() as conn:
                    conn.execute(sync_sa.text("SELECT 1"))
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.fail("PostgreSQL failed to start")

        import alembic.command
        import alembic.config

        alembic_cfg = alembic.config.Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic.command.upgrade(alembic_cfg, "head")

        yield async_url

    finally:
        subprocess.check_call(["docker", "rm", "-f", container_name], timeout=10.0)


@pytest.fixture
async def postgres_db(postgres_url):
    engine = create_async_engine(postgres_url, echo=False)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # clear tables before each test
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    # Insert required foreign key relations
    from alpha_core.db.models import ProjectRecord

    async with engine.begin() as conn:
        await conn.execute(
            sa.insert(ProjectRecord).values(id="test_proj", name="test", repo_path="/test")
        )

    yield SessionFactory
    await engine.dispose()


def utc_now() -> datetime:
    return datetime.now(UTC)


@pytest.mark.asyncio
async def test_approval_task_submission_preserves_postgres_fk_order(postgres_db):
    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="test_proj",
        repo="/test",
        objective="Prove task row exists before pending approval insert",
        allowed_paths=["proof.txt"],
        requires_approval=True, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    async with postgres_db() as session:
        task = await TaskEngine.submit_task(session, envelope)
        await session.commit()

    async with postgres_db() as session:
        persisted_task = await session.get(TaskRecord, task_id)
        approval = await session.scalar(
            sa.select(ApprovalRecord).where(ApprovalRecord.task_id == task_id)
        )

    assert task.status == TaskStatus.WAITING_APPROVAL.value
    assert persisted_task is not None
    assert approval is not None
    assert approval.status == "pending"


@pytest.mark.asyncio
async def test_verified_result_preserves_attempt_review_fk_order(postgres_db):
    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    attempt_id = f"att_{uuid.uuid4().hex[:8]}"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="test_proj",
        repo="/test",
        objective="Prove attempt row exists before pending review approval insert",
        allowed_paths=["proof.txt"],
        require_packet_binding=True, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    async with postgres_db() as session:
        await TaskEngine.submit_task(session, envelope)
        leased = await TaskEngine.lease_next_task(session, "worker_one")
        assert leased is not None
        task, _ = leased
        result = TaskResult(
            task_id=task_id,
            attempt_id=attempt_id,
            status=TaskStatus.COMPLETED,
            agent=AgentType.ANTIGRAVITY,
            model="gemini-3.1-pro-high",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            result_commit="result_commit",
            files_changed=["proof.txt"],
            packet_sha256=compute_packet_digest(envelope),
            gate_result=GateResult(
                task_id=task_id,
                attempt_id=attempt_id,
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="evi_result_order_lint",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Lint gate passed",
                    ),
                    GateEvidence(
                        evidence_id="evi_result_order_unit",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Unit gate passed",
                    ),
                ],
            ),
        )
        assert await TaskEngine.submit_result(session, result, task.lease_token, "worker_one")
        await session.commit()

    async with postgres_db() as session:
        attempt = await session.get(AttemptRecord, attempt_id)
        approval = await session.scalar(
            sa.select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_id,
                ApprovalRecord.attempt_id == attempt_id,
                ApprovalRecord.approval_type == "task_review",
            )
        )

    assert attempt is not None
    assert approval is not None
    assert approval.status == "pending"


@pytest.mark.asyncio
async def test_expired_lease_exactly_once(postgres_db):
    async with postgres_db() as setup_session:
        task_id = f"tsk_{uuid.uuid4().hex[:8]}"
        task = TaskRecord(
            id=task_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.LEASED.value,
            lease_token="lease_123",
            worker_id="worker_1",
            lease_expires_at=utc_now() - timedelta(minutes=5),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        setup_session.add(task)
        await setup_session.commit()

    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def session_a():
        async with postgres_db() as session:
            async with session.begin():
                count = await TaskEngine.timeout_expired_leases(session)
                lock_held.set()
                await asyncio.wait_for(release_lock.wait(), timeout=5.0)
                return count

    async def session_b():
        await asyncio.wait_for(lock_held.wait(), timeout=5.0)
        async with postgres_db() as session:
            async with session.begin():
                count = await asyncio.wait_for(
                    TaskEngine.timeout_expired_leases(session), timeout=5.0
                )
                assert count == 0
                release_lock.set()
                return count

    res_a, res_b = await asyncio.wait_for(asyncio.gather(session_a(), session_b()), timeout=5.0)
    assert res_a == 1
    assert res_b == 0

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.RETRYABLE_FAILED.value
        assert task.lease_token is None
        assert task.worker_id is None

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == task_id)
        )
        events = events_res.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "task_retry_scheduled"


@pytest.mark.asyncio
async def test_due_retry_exactly_once(postgres_db):
    async with postgres_db() as setup_session:
        task_id = f"tsk_{uuid.uuid4().hex[:8]}"
        task = TaskRecord(
            id=task_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RETRYABLE_FAILED.value,
            next_eligible_at=utc_now() - timedelta(minutes=5),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        setup_session.add(task)
        await setup_session.commit()

    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def session_a():
        async with postgres_db() as session:
            async with session.begin():
                count = await TaskEngine.release_due_retries(session)
                lock_held.set()
                await asyncio.wait_for(release_lock.wait(), timeout=5.0)
                return count

    async def session_b():
        await asyncio.wait_for(lock_held.wait(), timeout=5.0)
        async with postgres_db() as session:
            async with session.begin():
                count = await asyncio.wait_for(TaskEngine.release_due_retries(session), timeout=5.0)
                assert count == 0
                release_lock.set()
                return count

    res_a, res_b = await asyncio.wait_for(asyncio.gather(session_a(), session_b()), timeout=5.0)
    assert res_a == 1
    assert res_b == 0

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.QUEUED.value
        assert task.next_eligible_at is None

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == task_id)
        )
        events = events_res.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "task_requeued_from_retry"


@pytest.mark.asyncio
async def test_stalled_task_exactly_once(postgres_db):
    async with postgres_db() as setup_session:
        task_id = f"tsk_{uuid.uuid4().hex[:8]}"
        task = TaskRecord(
            id=task_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RUNNING.value,
            lease_token="lease_123",
            worker_id="worker_1",
            leased_at=utc_now() - timedelta(minutes=15),
            updated_at=utc_now() - timedelta(minutes=15),
            lease_expires_at=utc_now() + timedelta(minutes=60),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        setup_session.add(task)
        await setup_session.commit()

    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def session_a():
        async with postgres_db() as session:
            async with session.begin():
                processed_ids = await TaskEngine.check_watchdog_stalls(
                    session, stall_timeout_seconds=300
                )
                lock_held.set()
                await asyncio.wait_for(release_lock.wait(), timeout=5.0)
                return len(processed_ids)

    async def session_b():
        await asyncio.wait_for(lock_held.wait(), timeout=5.0)
        async with postgres_db() as session:
            async with session.begin():
                processed_ids = await asyncio.wait_for(
                    TaskEngine.check_watchdog_stalls(session, stall_timeout_seconds=300),
                    timeout=5.0,
                )
                assert len(processed_ids) == 0
                release_lock.set()
                return len(processed_ids)

    res_a, res_b = await asyncio.wait_for(asyncio.gather(session_a(), session_b()), timeout=5.0)
    assert res_a == 1
    assert res_b == 0

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.RETRYABLE_FAILED.value

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == task_id)
        )
        events = events_res.scalars().all()
        assert len(events) == 2
        event_types = {e.event_type for e in events}
        assert event_types == {"task_stalled_retrying", "task_retry_scheduled"}


@pytest.mark.asyncio
async def test_healthy_active_row_not_locked(postgres_db):
    async with postgres_db() as setup_session:
        stalled_id = f"tsk_stalled_{uuid.uuid4().hex[:8]}"
        healthy_id = f"tsk_healthy_{uuid.uuid4().hex[:8]}"

        stalled_task = TaskRecord(
            id=stalled_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RUNNING.value,
            lease_token="lease_stalled",
            worker_id="worker_1",
            leased_at=utc_now() - timedelta(minutes=15),
            updated_at=utc_now() - timedelta(minutes=15),
            lease_expires_at=utc_now() + timedelta(minutes=60),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        healthy_task = TaskRecord(
            id=healthy_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RUNNING.value,
            lease_token="lease_healthy",
            worker_id="worker_1",
            leased_at=utc_now(),  # fresh lease
            updated_at=utc_now(),
            lease_expires_at=utc_now() + timedelta(minutes=60),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        setup_session.add_all([stalled_task, healthy_task])
        await setup_session.commit()

    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def hold_recovery_lock():
        async with postgres_db() as session:
            async with session.begin():
                await TaskEngine.check_watchdog_stalls(session, stall_timeout_seconds=300)
                lock_held.set()
                try:
                    await asyncio.wait_for(release_lock.wait(), timeout=5.0)
                finally:
                    pass

    async def update_healthy():
        await asyncio.wait_for(lock_held.wait(), timeout=5.0)
        try:
            async with postgres_db() as session:
                success = await asyncio.wait_for(
                    TaskEngine.record_heartbeat(
                        session, healthy_id, lease_token="lease_healthy", worker_id="worker_1"
                    ),
                    timeout=0.5,
                )
                assert success
        finally:
            release_lock.set()

    await asyncio.wait_for(asyncio.gather(hold_recovery_lock(), update_healthy()), timeout=5.0)


@pytest.mark.asyncio
async def test_future_retry_not_locked(postgres_db):
    async with postgres_db() as setup_session:
        due_id = f"tsk_due_{uuid.uuid4().hex[:8]}"
        future_id = f"tsk_future_{uuid.uuid4().hex[:8]}"

        due_task = TaskRecord(
            id=due_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RETRYABLE_FAILED.value,
            next_eligible_at=utc_now() - timedelta(minutes=15),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        future_task = TaskRecord(
            id=future_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RETRYABLE_FAILED.value,
            next_eligible_at=utc_now() + timedelta(minutes=60),  # future
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        setup_session.add_all([due_task, future_task])
        await setup_session.commit()

    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def hold_recovery_lock():
        async with postgres_db() as session:
            async with session.begin():
                await TaskEngine.release_due_retries(session)
                lock_held.set()
                try:
                    await asyncio.wait_for(release_lock.wait(), timeout=5.0)
                finally:
                    pass

    async def update_future():
        await asyncio.wait_for(lock_held.wait(), timeout=5.0)
        try:

            async def competing_tx():
                async with postgres_db() as session:
                    async with session.begin():
                        task = await session.get(TaskRecord, future_id)
                        task.next_eligible_at = utc_now() + timedelta(minutes=120)
                        await session.flush()
                        await session.commit()

            await asyncio.wait_for(competing_tx(), timeout=0.5)
        finally:
            release_lock.set()

    await asyncio.wait_for(asyncio.gather(hold_recovery_lock(), update_future()), timeout=5.0)

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, future_id)
        assert task.status == TaskStatus.RETRYABLE_FAILED.value
        assert task.next_eligible_at > utc_now() + timedelta(minutes=110)

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == future_id)
        )
        events = events_res.scalars().all()
        assert len(events) == 0


@pytest.mark.asyncio
async def test_skip_locked_behavior(postgres_db):
    async with postgres_db() as setup_session:
        task_id = f"tsk_skip_{uuid.uuid4().hex[:8]}"
        task = TaskRecord(
            id=task_id,
            project_id="test_proj",
            repo="/test",
            objective="test objective",
            status=TaskStatus.RETRYABLE_FAILED.value,
            next_eligible_at=utc_now() - timedelta(minutes=5),
            details_json={
                "task_id": "test_id",
                "project_id": "test_proj",
                "repo": "/test",
                "objective": "test objective",
                "allowed_paths": ["."],
            },
            depends_on_json=[],
            max_attempts=3,
        )
        setup_session.add(task)
        await setup_session.commit()

    lock_acquired = asyncio.Event()
    release_lock = asyncio.Event()

    async def session_a():
        async with postgres_db() as session:
            async with session.begin():
                await session.execute(
                    sa.select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
                )
                lock_acquired.set()
                try:
                    await asyncio.wait_for(release_lock.wait(), timeout=5.0)
                finally:
                    pass

    async def session_b():
        await asyncio.wait_for(lock_acquired.wait(), timeout=5.0)
        try:
            async with postgres_db() as session:
                async with session.begin():
                    count = await asyncio.wait_for(
                        TaskEngine.release_due_retries(session), timeout=5.0
                    )
                    assert count == 0
        finally:
            release_lock.set()

    await asyncio.wait_for(asyncio.gather(session_a(), session_b()), timeout=5.0)

    # After A releases the lock, B (or anyone) should be able to process it
    async with postgres_db() as check_session:
        async with check_session.begin():
            count = await TaskEngine.release_due_retries(check_session)
            assert count == 1
