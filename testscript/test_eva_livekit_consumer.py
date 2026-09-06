"""
testscript/test_eva_livekit_consumer.py
Unit tests verifying the Eva LiveKit read-only consumer and autonomous spec extraction loop.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from alpha_core.eva.livekit_consumer import EvaLiveKitConsumer
from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_protocol.enums import GateType


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_eva_consumer_ingest_and_trigger_extraction():
    mock_extractor = MagicMock()
    mock_extractor.extract_from_transcript.return_value = ExtractedSpecification(
        title="Add PostgreSQL Connection Pooling",
        summary="Configure SQLAlchemy async engine pool size and max overflow.",
        requirements=["Set pool_size=10", "Set max_overflow=20"],
        acceptance_criteria=["Verify connection reuse in concurrent benchmarks"],
        allowed_paths=["alpha_core/db/connection.py"],
        is_actionable=True,
        confidence_score=0.92,
    )

    callback_mock = MagicMock()

    consumer = EvaLiveKitConsumer(
        room_name="test-boardroom",
        project_id="prj_alpha_db",
        spec_extractor=mock_extractor,
        on_task_proposed=callback_mock,
    )

    # Ingest dialogue
    consumer.ingest_transcript_line(
        "u_ajay", "Ajay (Founder)", "We need connection pooling on PostgreSQL."
    )
    consumer.ingest_transcript_line("u_client", "Client", "Agreed, let us cap pool size to 10.")

    # Trigger extraction manually
    envelope = await consumer.trigger_extraction()

    assert envelope is not None
    assert envelope.task_id.startswith("tsk_eva_")
    assert envelope.project_id == "prj_alpha_db"
    assert envelope.objective == "Add PostgreSQL Connection Pooling"
    assert envelope.allowed_paths == ["alpha_core/db/connection.py"]
    assert GateType.UNIT_TEST in envelope.acceptance_plan.required_gates
    assert len(consumer.proposed_tasks) == 1
    callback_mock.assert_called_once_with(envelope)


@pytest.mark.asyncio
async def test_eva_consumer_ignores_non_actionable_dialogue():
    mock_extractor = MagicMock()
    mock_extractor.extract_from_transcript.return_value = ExtractedSpecification(
        title="Smalltalk",
        summary="Greeting and weather",
        is_actionable=False,
        confidence_score=0.2,
    )

    consumer = EvaLiveKitConsumer(
        room_name="test-boardroom",
        project_id="prj_test",
        spec_extractor=mock_extractor,
    )

    consumer.ingest_transcript_line("u1", "Ajay", "Hello, good morning.")
    envelope = await consumer.trigger_extraction()

    assert envelope is None
    assert len(consumer.proposed_tasks) == 0


@pytest.mark.asyncio
async def test_eva_consumer_start_stop_lifecycle():
    consumer = EvaLiveKitConsumer(
        room_name="test-room",
        project_id="prj_test",
    )

    # Mock internal LiveKit Room connect/disconnect
    consumer.room.connect = AsyncMock()
    consumer.room.disconnect = AsyncMock()
    consumer.room.isconnected = MagicMock(return_value=True)

    await consumer.start()
    assert consumer._is_running is True
    assert consumer._loop_task is not None
    assert consumer.room.connect.called

    await consumer.stop()
    assert consumer._is_running is False
    assert consumer._loop_task is None
    assert consumer.room.disconnect.called
