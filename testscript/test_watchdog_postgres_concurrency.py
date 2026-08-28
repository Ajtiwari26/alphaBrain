import asyncio
import subprocess
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.db.models import AuditEventRecord, Base, TaskRecord
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import TaskStatus

# Check for Docker before running
try:
    subprocess.check_output(["docker", "info"], stderr=subprocess.STDOUT)
    DOCKER_AVAILABLE = True
except Exception:
    DOCKER_AVAILABLE = False


@pytest.fixture(scope="session")
def postgres_url():
    if not DOCKER_AVAILABLE:
        pytest.fail("Docker is required for real PostgreSQL concurrency proofs")

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
            "5432",
            "-d",
            "postgres:17",
        ]
    )

    try:
        import time

        port_out = (
            subprocess.check_output(["docker", "port", container_name, "5432/tcp"]).decode().strip()
        )
        first_line = port_out.split("\n")[0]
        host_port = first_line.split(":")[1]

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
        subprocess.check_call(["docker", "rm", "-f", container_name])


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

    async def run_recovery():
        async with postgres_db() as session:
            async with session.begin():
                count = await TaskEngine.timeout_expired_leases(session)
                return count

    # Run concurrently
    results = await asyncio.gather(run_recovery(), run_recovery())

    assert sorted(results) == [0, 1]

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.RETRYABLE_FAILED.value
        assert task.lease_token is None
        assert task.worker_id is None

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == task_id)
        )
        events = events_res.scalars().all()
        # Should have lease_expired_requeued and task_retry_scheduled
        assert len(events) == 1


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

    async def run_recovery():
        async with postgres_db() as session:
            async with session.begin():
                count = await TaskEngine.release_due_retries(session)
                return count

    # Run concurrently
    results = await asyncio.gather(run_recovery(), run_recovery())

    assert sorted(results) == [0, 1]

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.QUEUED.value
        assert task.next_eligible_at is None

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == task_id)
        )
        events = events_res.scalars().all()
        # Should have one task_requeued_from_retry
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

    async def run_recovery():
        async with postgres_db() as session:
            async with session.begin():
                processed_ids = await TaskEngine.check_watchdog_stalls(
                    session, stall_timeout_seconds=300
                )
                return len(processed_ids)

    # Run concurrently
    results = await asyncio.gather(run_recovery(), run_recovery())

    assert sorted(results) == [0, 1]

    async with postgres_db() as check_session:
        task = await check_session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.RETRYABLE_FAILED.value

        events_res = await check_session.execute(
            sa.select(AuditEventRecord).where(AuditEventRecord.task_id == task_id)
        )
        events = events_res.scalars().all()
        # Should have task_stalled_retrying and task_retry_scheduled
        assert len(events) == 2


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

    event = asyncio.Event()

    async def hold_recovery_lock():
        async with postgres_db() as session:
            async with session.begin():
                await TaskEngine.check_watchdog_stalls(session, stall_timeout_seconds=300)
                event.set()
                await asyncio.sleep(0.5)  # Hold the lock

    async def update_healthy():
        await event.wait()  # Wait until recovery holds its lock
        async with postgres_db() as session:
            # Attempt to record heartbeat, this must not block
            success = await TaskEngine.record_heartbeat(
                session, healthy_id, lease_token="lease_healthy", worker_id="worker_1"
            )
            assert success

    await asyncio.gather(hold_recovery_lock(), update_healthy())


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

    event = asyncio.Event()

    async def hold_recovery_lock():
        async with postgres_db() as session:
            async with session.begin():
                await TaskEngine.release_due_retries(session)
                event.set()
                await asyncio.sleep(0.5)  # Hold the lock

    async def update_future():
        await event.wait()  # Wait until recovery holds its lock
        async with postgres_db() as session:
            async with session.begin():
                task = await session.get(TaskRecord, future_id)
                task.next_eligible_at = utc_now() + timedelta(minutes=120)
                await session.flush()

    await asyncio.gather(hold_recovery_lock(), update_future())


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

    async def session_a():
        async with postgres_db() as session:
            async with session.begin():
                # Explicitly lock the row
                await session.execute(
                    sa.select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
                )
                lock_acquired.set()
                await asyncio.sleep(1.0)  # Hold lock long enough for B to attempt

    async def session_b():
        await lock_acquired.wait()
        async with postgres_db() as session:
            async with session.begin():
                # Must not block, must skip locked row
                count = await TaskEngine.release_due_retries(session)
                assert count == 0

    await asyncio.gather(session_a(), session_b())

    # After A releases the lock, B (or anyone) should be able to process it
    async with postgres_db() as check_session:
        async with check_session.begin():
            count = await TaskEngine.release_due_retries(check_session)
            assert count == 1
