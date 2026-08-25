"""
testscript/test_state_engine.py
Automated tests for database engine, task lifecycle, atomic leasing, and evidence gates.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.db.models import Base
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateEvidence,
    GateResult,
    GateType,
    RiskClass,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)


@pytest_asyncio.fixture
async def test_db_session():
    # Use in-memory SQLite for superfast isolated tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_task_submission_and_leasing(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_001",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Create core database models",
        allowed_paths=["."],
        risk_class=RiskClass.LOW,
        acceptance_plan=AcceptancePlan(required_gates=[GateType.UNIT_TEST]),
        preferred_agent=AgentType.ANTIGRAVITY,
    )

    # 1. Submit task
    task = await TaskEngine.submit_task(test_db_session, envelope)
    assert task.id == "tsk_state_001"
    assert task.status == TaskStatus.QUEUED.value

    # 2. Lease task
    leased_tuple = await TaskEngine.lease_next_task(test_db_session, worker_id="mac_worker_1")
    assert leased_tuple is not None
    leased_task, leased_envelope = leased_tuple
    assert leased_task.id == "tsk_state_001"
    assert leased_task.status == TaskStatus.LEASED.value
    assert leased_task.lease_token is not None
    assert leased_envelope.objective == "Create core database models"

    # 3. Trying to lease again should return None (already leased)
    empty_lease = await TaskEngine.lease_next_task(test_db_session, worker_id="mac_worker_2")
    assert empty_lease is None


@pytest.mark.asyncio
async def test_result_submission_with_gates(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_002",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Implement authentication middleware",
        allowed_paths=["auth.py"],
        preferred_agent=AgentType.ANTIGRAVITY,
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    lease = await TaskEngine.lease_next_task(test_db_session, worker_id="mac_worker_1")
    assert lease is not None
    leased_task, _ = lease

    # Construct successful gate evidence
    gate_evidence = GateEvidence(
        evidence_id="evi_state_01",
        gate_type=GateType.UNIT_TEST,
        passed=True,
        summary="All tests passed",
    )
    gate_result = GateResult(
        task_id="tsk_state_002",
        attempt_id="att_state_002_1",
        all_passed=True,
        evidence_items=[gate_evidence],
    )

    result = TaskResult(
        attempt_id="att_state_002_1",
        task_id="tsk_state_002",
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit="HEAD",
        result_commit="commit_abc123",
        files_changed=["auth.py"],
        gate_result=gate_result,
    )

    # Submit result
    success = await TaskEngine.submit_result(test_db_session, result, leased_task.lease_token)
    assert success is True
    assert leased_task.status == TaskStatus.VERIFIED.value
