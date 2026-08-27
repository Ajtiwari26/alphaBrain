import traceback
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.db.models import (
    AuditEventRecord,
    Base,
    GateEvidenceRecord,
    TaskRecord,
)
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol.gates import AcceptancePlan, GateEvidence, GateResult, GateType
from alpha_protocol.task import TaskEnvelope, TaskResult, TaskStatus


@pytest_asyncio.fixture(scope="function")
async def test_db_session():
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true", echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_submit_gate_evidence_verified_and_failed(test_db_session):
    try:
        session = test_db_session
        task = TaskRecord(
            id="tsk_123",
            project_id="prj_1",
            repo="/tmp/repo",
            objective="test",
            details_json=TaskEnvelope(
                task_id="tsk_123",
                project_id="prj_1",
                repo="/tmp",
                objective="obj",
                base_commit="abcd",
                allowed_paths=["."],
                acceptance_plan=AcceptancePlan(commands=[]),
            ).model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="tkn",
            worker_id="wrk_1",
            lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task)
        await session.commit()

        res = TaskResult(
            attempt_id="att_1",
            task_id="tsk_123",
            status=TaskStatus.VERIFIED,
            agent="codex",
            model="gemini",
            base_commit="abcd",
            gate_result=GateResult(
                task_id="tsk_123",
                attempt_id="att_1",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="ev_1",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Unit test passed",
                        output_log="log1",
                    ),
                    GateEvidence(
                        evidence_id="ev_2",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Lint passed",
                        output_log="log2",
                    ),
                ],
            ),
        )
        success = await TaskEngine.submit_result(session, res, "tkn", "wrk_1")
        assert success is True

        ev_query = await session.execute(
            select(GateEvidenceRecord).where(GateEvidenceRecord.task_id == "tsk_123")
        )
        evidence_records = ev_query.scalars().all()
        assert len(evidence_records) == 2

        types = {ev.gate_type for ev in evidence_records}
        assert types == {"unit_test", "lint"}

        success_dup = await TaskEngine.submit_result(session, res, "tkn", "wrk_1")
        assert success_dup is True
        ev_query_dup = await session.execute(
            select(GateEvidenceRecord).where(GateEvidenceRecord.task_id == "tsk_123")
        )
        assert len(ev_query_dup.scalars().all()) == 2

        task2 = TaskRecord(
            id="tsk_124",
            project_id="prj_1",
            repo="/tmp/repo",
            objective="test",
            details_json=TaskEnvelope(
                task_id="tsk_124",
                project_id="prj_1",
                repo="/tmp",
                objective="obj",
                base_commit="abcd",
                allowed_paths=["."],
                acceptance_plan=AcceptancePlan(commands=[]),
            ).model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="tkn2",
            worker_id="wrk_1",
            lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task2)
        await session.commit()

        res_fail = TaskResult(
            attempt_id="att_2",
            task_id="tsk_124",
            status=TaskStatus.RETRYABLE_FAILED,
            agent="codex",
            model="gemini",
            base_commit="abcd",
            gate_result=GateResult(
                task_id="tsk_124",
                attempt_id="att_2",
                all_passed=False,
                evidence_items=[
                    GateEvidence(
                        evidence_id="ev_3",
                        gate_type=GateType.UNIT_TEST,
                        passed=False,
                        summary="Unit test failed",
                        output_log="fail log",
                    )
                ],
            ),
        )
        success_fail = await TaskEngine.submit_result(session, res_fail, "tkn2", "wrk_1")
        assert success_fail is True

        ev_query_fail = await session.execute(
            select(GateEvidenceRecord).where(GateEvidenceRecord.task_id == "tsk_124")
        )
        assert len(ev_query_fail.scalars().all()) == 1

        audit_query = await session.execute(
            select(AuditEventRecord)
            .where(AuditEventRecord.task_id == "tsk_124")
            .where(AuditEventRecord.event_type == "result_submitted")
        )
        audit_rec = audit_query.scalars().first()
        assert audit_rec.details_json.get("agent") == "codex"

    except Exception as e:
        traceback.print_exc()
        raise e


@pytest.mark.asyncio
async def test_duplicate_evidence_id_across_attempts(test_db_session):
    try:
        session = test_db_session

        # Task 1
        task1 = TaskRecord(
            id="tsk_1",
            project_id="prj_1",
            repo="/tmp/repo",
            objective="test1",
            details_json=TaskEnvelope(
                task_id="tsk_1",
                project_id="prj_1",
                repo="/tmp",
                objective="obj",
                base_commit="abcd",
                allowed_paths=["."],
                acceptance_plan=AcceptancePlan(commands=[]),
            ).model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="tkn1",
            worker_id="wrk_1",
            lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task1)

        # Task 2
        task2 = TaskRecord(
            id="tsk_2",
            project_id="prj_1",
            repo="/tmp/repo",
            objective="test2",
            details_json=TaskEnvelope(
                task_id="tsk_2",
                project_id="prj_1",
                repo="/tmp",
                objective="obj",
                base_commit="abcd",
                allowed_paths=["."],
                acceptance_plan=AcceptancePlan(commands=[]),
            ).model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="tkn2",
            worker_id="wrk_1",
            lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task2)
        await session.commit()

        # Result 1 with evi_1
        res1 = TaskResult(
            attempt_id="att_1",
            task_id="tsk_1",
            status=TaskStatus.VERIFIED,
            agent="codex",
            model="gemini",
            base_commit="abcd",
            gate_result=GateResult(
                task_id="tsk_1",
                attempt_id="att_1",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="evi_1",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Test 1",
                        output_log="log1",
                    )
                ],
            ),
        )
        assert await TaskEngine.submit_result(session, res1, "tkn1", "wrk_1") is True

        # Result 2 with evi_1 (different attempt)
        res2 = TaskResult(
            attempt_id="att_2",
            task_id="tsk_2",
            status=TaskStatus.VERIFIED,
            agent="codex",
            model="gemini",
            base_commit="abcd",
            gate_result=GateResult(
                task_id="tsk_2",
                attempt_id="att_2",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="evi_1",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Test 2",
                        output_log="log2",
                    )
                ],
            ),
        )
        assert await TaskEngine.submit_result(session, res2, "tkn2", "wrk_1") is True

        # Assert both persisted successfully
        evs = await session.execute(select(GateEvidenceRecord))
        all_evs = evs.scalars().all()
        assert len(all_evs) == 2
        ids = {ev.id for ev in all_evs}
        assert "ev_Jnq9YjOsdklPhGbjkGmi76NaMvMMjS1Kd6nm_7QPPz4" in ids
        assert "ev_6FXYQlr5Owq1FZ2RZIdACegk8YcV5Pw_LrBpzVGV1TM" in ids

        # Repeat first exact submission
        assert await TaskEngine.submit_result(session, res1, "tkn1", "wrk_1") is True

        # Count stays unchanged
        evs_after = await session.execute(select(GateEvidenceRecord))
        assert len(evs_after.scalars().all()) == 2

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise e


@pytest.mark.asyncio
async def test_duplicate_evidence_id_long_attempt_ids(test_db_session):
    try:
        session = test_db_session

        # Two very long attempt IDs identical in first 64 chars
        prefix = "att_" + "a" * 60
        att_long_1 = prefix + "_01"
        att_long_2 = prefix + "_02"

        # Task 3
        task3 = TaskRecord(
            id="tsk_3",
            project_id="prj_1",
            repo="/tmp/repo",
            objective="test3",
            details_json=TaskEnvelope(
                task_id="tsk_3",
                project_id="prj_1",
                repo="/tmp",
                objective="obj",
                base_commit="abcd",
                allowed_paths=["."],
                acceptance_plan=AcceptancePlan(commands=[]),
            ).model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="tkn3",
            worker_id="wrk_1",
            lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task3)

        # Task 4
        task4 = TaskRecord(
            id="tsk_4",
            project_id="prj_1",
            repo="/tmp/repo",
            objective="test4",
            details_json=TaskEnvelope(
                task_id="tsk_4",
                project_id="prj_1",
                repo="/tmp",
                objective="obj",
                base_commit="abcd",
                allowed_paths=["."],
                acceptance_plan=AcceptancePlan(commands=[]),
            ).model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="tkn4",
            worker_id="wrk_1",
            lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(task4)
        await session.commit()

        # Result 3 with evi_1
        res3 = TaskResult(
            attempt_id=att_long_1,
            task_id="tsk_3",
            status=TaskStatus.VERIFIED,
            agent="codex",
            model="gemini",
            base_commit="abcd",
            gate_result=GateResult(
                task_id="tsk_3",
                attempt_id=att_long_1,
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="evi_1",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Test 3",
                        output_log="log3",
                    )
                ],
            ),
        )
        assert await TaskEngine.submit_result(session, res3, "tkn3", "wrk_1") is True

        # Result 4 with evi_1
        res4 = TaskResult(
            attempt_id=att_long_2,
            task_id="tsk_4",
            status=TaskStatus.VERIFIED,
            agent="codex",
            model="gemini",
            base_commit="abcd",
            gate_result=GateResult(
                task_id="tsk_4",
                attempt_id=att_long_2,
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="evi_1",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Test 4",
                        output_log="log4",
                    )
                ],
            ),
        )
        assert await TaskEngine.submit_result(session, res4, "tkn4", "wrk_1") is True

        # Assert both persisted successfully and are distinct
        evs = await session.execute(
            select(GateEvidenceRecord).where(GateEvidenceRecord.task_id.in_(["tsk_3", "tsk_4"]))
        )
        all_evs = evs.scalars().all()
        assert len(all_evs) == 2
        ids = {ev.id for ev in all_evs}
        assert len(ids) == 2
        assert all(len(i) <= 64 for i in ids)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise e
