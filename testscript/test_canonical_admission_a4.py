import pytest
from pydantic import ValidationError

from alpha_protocol.task import TaskEnvelope


@pytest.mark.xfail(reason="R2-R6 gap pending")
def test_task_envelope_rejects_head():
    with pytest.raises(ValidationError) as exc:
        TaskEnvelope(
            task_id="tsk_123",
            project_id="prj_alpha",
            repo=".",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            objective="Test objective",
            allowed_paths=["."],
        )
    assert "base_commit must be a resolved 40-char SHA" in str(exc.value)


def test_task_envelope_rejects_empty():
    with pytest.raises(ValidationError) as exc:
        TaskEnvelope(
            task_id="tsk_123",
            project_id="prj_alpha",
            repo=".",
            base_commit="",
            objective="Test objective",
            allowed_paths=["."],
        )
    assert "base_commit must be a resolved 40-char SHA" in str(exc.value)


def test_task_envelope_rejects_invalid_sha_length():
    with pytest.raises(ValidationError) as exc:
        TaskEnvelope(
            task_id="tsk_123",
            project_id="prj_alpha",
            repo=".",
            base_commit="1234567890abcdef1234567890abcdef1234567",  # 39 chars
            objective="Test objective",
            allowed_paths=["."],
        )
    assert "String should match pattern" in str(exc.value)


def test_task_envelope_rejects_invalid_sha_chars():
    with pytest.raises(ValidationError) as exc:
        TaskEnvelope(
            task_id="tsk_123",
            project_id="prj_alpha",
            repo=".",
            base_commit="g234567890abcdef1234567890abcdef12345678",  # invalid char 'g'
            objective="Test objective",
            allowed_paths=["."],
        )
    assert "String should match pattern" in str(exc.value)


def test_task_envelope_accepts_valid_sha():
    envelope = TaskEnvelope(
        task_id="tsk_123",
        project_id="prj_alpha",
        repo=".",
        base_commit="1234567890abcdef1234567890abcdef12345678",  # 40 chars
        objective="Test objective",
        allowed_paths=["."],
    )
    assert envelope.base_commit == "1234567890abcdef1234567890abcdef12345678"
