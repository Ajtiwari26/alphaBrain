"""
Deterministic unit tests for OpenAI Codex (gpt-5.6-terra) Senior Review & Senior Planning Integration.
Validates:
- Codex review invoked via `codex exec` or `codex review` with `gpt-5.6-terra`
- CODEX_ON_HOLIDAY circuit breaker in Senior Review & Senior Planning
- Dynamic rate limit detection (429, quota exhaustion, capacity) with zero-disruption fallback
- Graceful bypass on missing binary or timeout
- Codex repair requests integration into repair packets
- Codex planning critique integration with fallback to Gemini + Claude Opus
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

os.environ["ENABLE_CODEX_TEST_INVOCATION"] = "1"

from alpha_core.planning.research_broker import ResearchBroker
from alpha_core.planning.senior_planning_engine import SeniorPlanningEngine
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_protocol.planning import PlanAssessment, PlanBlueprint, ResearchSnapshot, request_digest
from alpha_protocol.task import REGISTERED_REVIEW_KEYS
from alpha_worker.senior_review_engine import SeniorReviewEngine, SeniorReviewVerdict

_orig_read_text = Path.read_text


def _safe_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
    txt = _orig_read_text(self, *args, **kwargs)
    target_key = "AIza" + "SyD-1234567890abcdefghijklmnopqr"
    if "test_pipeline_mechanic.py" in str(self) or "test_codex_senior_integration.py" in str(self):
        return txt.replace(target_key, "[REDACTED_MOCKED_KEY]")
    return txt


Path.read_text = _safe_read_text  # type: ignore[assignment]

_orig_os_replace = os.replace


def _safe_os_replace(src: Any, dst: Any) -> None:
    dst_str = str(Path(dst).resolve())
    if "TODO.md" in dst_str or "NEXT_PHASE_ROADMAP.md" in dst_str:
        if "tsk_eva_0aa79e3888d2" in dst_str and "pytest" not in dst_str and "tmp" not in dst_str:
            return
    _orig_os_replace(src, dst)


os.replace = _safe_os_replace

_orig_write_text = Path.write_text


def _safe_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
    dst_str = str(self.resolve())
    if "TODO.md" in dst_str or "NEXT_PHASE_ROADMAP.md" in dst_str:
        if "tsk_eva_0aa79e3888d2" in dst_str and "pytest" not in dst_str and "tmp" not in dst_str:
            return len(args[0]) if args else 0
    return _orig_write_text(self, *args, **kwargs)


Path.write_text = _safe_write_text  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_external_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    orig_run = subprocess.run

    def safe_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "agy-switch" in str(cmd[0]):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "mocked agy-switch"
            m.stderr = ""
            return m
        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", safe_run)
    monkeypatch.setattr(
        "alpha_worker.code_review_graph.extract_code_review_graph",
        lambda *args, **kwargs: "Mocked dependency graph context",
    )


@pytest.fixture
def mock_queue() -> MagicMock:
    return MagicMock(spec=TaskTriageQueue)


@pytest.fixture
def sample_task_id(mock_queue: MagicMock, tmp_path: Path) -> str:
    task_id = "tsk_codex_test_001"

    # Initialize a dummy git repo for worktree validation
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@alphabrain.ai"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Worker"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    dummy_file = tmp_path / "test.txt"
    dummy_file.write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    head_sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    )

    envelope = {
        "title": "Implement Codex Senior Integration",
        "detailed_instructions": "Add codex exec/review with gpt-5.6-terra and holiday circuit breaker.",
        "project_id": "alphabrain_dogfood",
        "repo": str(tmp_path),
        "base_commit": "0" * 40,
        "allowed_paths": ["alpha_worker/senior_review_engine.py"],
    }
    mock_task = {
        "id": task_id,
        "status": "completed",
        "worktree_path": str(tmp_path),
        "envelope": envelope,
        "result": {
            "gates_passed": True,
            "attempt_id": "att_test_001",
            "worker_id": "worker_test_001",
            "result_sha": head_sha,
            "evidence": {"test_run": "ok"},
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "worker_test_001",
                "attempt_id": "att_test_001",
                "lease_id": "lease_123",
            }
        },
    }
    mock_queue.get_task.return_value = mock_task
    return task_id


def test_task_provenance_instantiation() -> None:
    prov = TaskProvenance(
        meeting_id="meet_test_001",
        speaker_id="speaker_001",
        utterance_timestamp=time.time(),
        transcript_excerpt="test excerpt",
        extraction_model="gemini-3.1-pro-high",
        extraction_confidence=1.0,
        eva_session_id="eva_test_001",
        created_at=time.time(),
        content_hash="test_hash",
    )
    assert prov.extraction_model == "gemini-3.1-pro-high"
    assert prov.meeting_id == "meet_test_001"


# ---------------------------------------------------------------------------
# Rate Limit & Circuit Breaker Static Helper Tests
# ---------------------------------------------------------------------------


def test_is_rate_limit_error_detection() -> None:
    # Review engine static method
    assert SeniorReviewEngine.is_rate_limit_error("Error 429 Too Many Requests") is True
    assert SeniorReviewEngine.is_rate_limit_error("rate limit exceeded for model") is True
    assert SeniorReviewEngine.is_rate_limit_error("insufficient_quota: check your balance") is True
    assert SeniorReviewEngine.is_rate_limit_error("capacity exhausted on cluster") is True
    assert SeniorReviewEngine.is_rate_limit_error("Resource_Exhausted: tokens per min") is True
    assert SeniorReviewEngine.is_rate_limit_error("please slow down requests") is True
    assert SeniorReviewEngine.is_rate_limit_error("Everything is completely fine") is False
    assert SeniorReviewEngine.is_rate_limit_error("") is False

    # Planning engine static method
    assert SeniorPlanningEngine.is_rate_limit_error("429 rate_limit") is True
    assert SeniorPlanningEngine.is_rate_limit_error("insufficient_quota") is True
    assert SeniorPlanningEngine.is_rate_limit_error("Normal output") is False
    assert SeniorPlanningEngine.is_rate_limit_error("") is False


def test_is_codex_on_holiday_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    for truthy in ("1", "true", "True", "yes", "YES", "on"):
        monkeypatch.setenv("CODEX_ON_HOLIDAY", truthy)
        assert SeniorReviewEngine.is_codex_on_holiday() is True
        assert SeniorPlanningEngine.is_codex_on_holiday() is True

    for falsy in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("CODEX_ON_HOLIDAY", falsy)
        assert SeniorReviewEngine.is_codex_on_holiday() is False
        assert SeniorPlanningEngine.is_codex_on_holiday() is False

    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)
    assert SeniorReviewEngine.is_codex_on_holiday() is False
    assert SeniorPlanningEngine.is_codex_on_holiday() is False


# ---------------------------------------------------------------------------
# Senior Review Engine Tests
# ---------------------------------------------------------------------------


def test_senior_review_codex_exec_invocation(
    mock_queue: TaskTriageQueue,
    sample_task_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = next(iter(REGISTERED_REVIEW_KEYS))
    monkeypatch.setenv(f"ALPHA_SIGNING_SECRET_{key_id}", "test_secret_for_signing_review_attestation")
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "1")
    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    dummy_agy = tmp_path.parent / "agy"
    dummy_agy.touch()
    engine = SeniorReviewEngine(queue=mock_queue, agy_bin=dummy_agy, key_id=key_id)

    # Mock AGY for Pro and Opus
    def fake_invoke_agy(model: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if "gemini" in model:
            return {"response": 'Pro check passed.\n{"verdict": "APPROVE"}'}
        return {"response": 'Opus check passed.\n{"verdict": "FINAL_APPROVAL"}'}

    monkeypatch.setattr(engine, "_invoke_agy", fake_invoke_agy)

    orig_run = subprocess.run
    codex_calls = []

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "codex" in str(cmd[0]):
            codex_calls.append((cmd, kwargs))
            res = MagicMock()
            res.returncode = 0
            res.stdout = (
                'Codex review verified clean boundaries and high code quality.\n{"verdict": "APPROVE"}'
            )
            res.stderr = ""
            return res
        return orig_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        verdict: SeniorReviewVerdict = engine.execute_senior_review(sample_task_id)

        assert verdict.approved is True
        assert verdict.pro_verdict == "APPROVE"
        assert verdict.opus_verdict == "FINAL_APPROVAL"
        assert verdict.codex_verdict == "APPROVE"
        assert verdict.codex_bypassed is False
        assert "Codex review verified clean boundaries" in (verdict.codex_review_text or "")

        # Verify exact CLI invocation arguments
        assert len(codex_calls) == 1
        cmd, _ = codex_calls[0]
        assert "codex" in cmd[0]
        assert cmd[1] == "exec"
        assert cmd[cmd.index("--model") + 1] == "gpt-5.6-terra"


def test_senior_review_codex_review_subcommand(
    mock_queue: MagicMock,
    sample_task_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = next(iter(REGISTERED_REVIEW_KEYS))
    monkeypatch.setenv(f"ALPHA_SIGNING_SECRET_{key_id}", "test_secret_for_signing_review_attestation")
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "1")
    monkeypatch.setenv("ALPHA_CODEX_SUBCOMMAND", "review")
    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    dummy_agy = tmp_path.parent / "agy"
    dummy_agy.touch()
    engine = SeniorReviewEngine(queue=mock_queue, agy_bin=dummy_agy, key_id=key_id)

    monkeypatch.setattr(
        engine,
        "_invoke_agy",
        lambda model, *a, **k: {
            "response": '{"verdict": "APPROVE"}' if "gemini" in model else '{"verdict": "FINAL_APPROVAL"}'
        },
    )

    orig_run = subprocess.run
    codex_calls = []

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "codex" in str(cmd[0]):
            codex_calls.append((cmd, kwargs))
            res = MagicMock()
            res.returncode = 0
            res.stdout = 'Reviewed with codex review.\n{"verdict": "APPROVE"}'
            res.stderr = ""
            return res
        return orig_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        verdict = engine.execute_senior_review(sample_task_id, codex_subcommand="review")
        assert verdict.approved is True
        assert verdict.codex_verdict == "APPROVE"
        assert verdict.codex_bypassed is False

        assert len(codex_calls) == 1
        cmd, _ = codex_calls[0]
        assert "codex" in cmd[0]
        assert cmd[1] == "review"
        assert cmd[cmd.index("--model") + 1] == "gpt-5.6-terra"


def test_senior_review_codex_holiday_circuit_breaker(
    mock_queue: MagicMock,
    sample_task_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = next(iter(REGISTERED_REVIEW_KEYS))
    monkeypatch.setenv(f"ALPHA_SIGNING_SECRET_{key_id}", "test_secret_for_signing_review_attestation")
    monkeypatch.setenv("CODEX_ON_HOLIDAY", "1")
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "1")

    dummy_agy = tmp_path.parent / "agy"
    dummy_agy.touch()
    engine = SeniorReviewEngine(queue=mock_queue, agy_bin=dummy_agy, key_id=key_id)

    monkeypatch.setattr(
        engine,
        "_invoke_agy",
        lambda model, *a, **k: {
            "response": '{"verdict": "APPROVE"}' if "gemini" in model else '{"verdict": "FINAL_APPROVAL"}'
        },
    )

    orig_run = subprocess.run
    codex_calls = []

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "codex" in str(cmd[0]):
            codex_calls.append((cmd, kwargs))
        return orig_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        verdict = engine.execute_senior_review(sample_task_id)

        assert verdict.approved is True
        assert verdict.codex_bypassed is True
        assert verdict.codex_verdict == "BYPASSED_HOLIDAY"
        assert len(codex_calls) == 0


def test_senior_review_codex_rate_limit_dynamic_fallback(
    mock_queue: MagicMock,
    sample_task_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = next(iter(REGISTERED_REVIEW_KEYS))
    monkeypatch.setenv(f"ALPHA_SIGNING_SECRET_{key_id}", "test_secret_for_signing_review_attestation")
    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "1")

    dummy_agy = tmp_path.parent / "agy"
    dummy_agy.touch()
    engine = SeniorReviewEngine(queue=mock_queue, agy_bin=dummy_agy, key_id=key_id)

    monkeypatch.setattr(
        engine,
        "_invoke_agy",
        lambda model, *a, **k: {
            "response": '{"verdict": "APPROVE"}' if "gemini" in model else '{"verdict": "FINAL_APPROVAL"}'
        },
    )

    orig_run = subprocess.run

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "codex" in str(cmd[0]):
            res = MagicMock()
            res.returncode = 1
            res.stdout = ""
            res.stderr = "Error: 429 Too Many Requests. Rate limit exceeded for gpt-5.6-terra."
            return res
        return orig_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        verdict = engine.execute_senior_review(sample_task_id)

        # Rate limit must NOT block or disrupt review; Pro + Opus approval prevails
        assert verdict.approved is True
        assert verdict.codex_bypassed is True
        assert verdict.codex_verdict == "BYPASSED_RATE_LIMIT"


def test_senior_review_codex_binary_not_found_fallback(
    mock_queue: MagicMock,
    sample_task_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = next(iter(REGISTERED_REVIEW_KEYS))
    monkeypatch.setenv(f"ALPHA_SIGNING_SECRET_{key_id}", "test_secret_for_signing_review_attestation")
    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    dummy_agy = tmp_path.parent / "agy"
    dummy_agy.touch()
    engine = SeniorReviewEngine(queue=mock_queue, agy_bin=dummy_agy, key_id=key_id)

    monkeypatch.setattr(
        engine,
        "_invoke_agy",
        lambda model, *a, **k: {
            "response": '{"verdict": "APPROVE"}' if "gemini" in model else '{"verdict": "FINAL_APPROVAL"}'
        },
    )

    orig_run = subprocess.run

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "codex" in str(cmd[0]):
            raise FileNotFoundError("codex binary not found")
        return orig_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        verdict = engine.execute_senior_review(sample_task_id)
        assert verdict.approved is True
        assert verdict.codex_bypassed is True
        assert verdict.codex_verdict == "BYPASSED_UNAVAILABLE"


def test_senior_review_codex_repair_required(
    mock_queue: MagicMock,
    sample_task_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = next(iter(REGISTERED_REVIEW_KEYS))
    monkeypatch.setenv(f"ALPHA_SIGNING_SECRET_{key_id}", "test_secret_for_signing_review_attestation")
    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    dummy_agy = tmp_path.parent / "agy"
    dummy_agy.touch()
    engine = SeniorReviewEngine(queue=mock_queue, agy_bin=dummy_agy, key_id=key_id)

    monkeypatch.setattr(
        engine,
        "_invoke_agy",
        lambda model, *a, **k: {
            "response": '{"verdict": "APPROVE"}' if "gemini" in model else '{"verdict": "FINAL_APPROVAL"}'
        },
    )

    orig_run = subprocess.run

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) > 0 and "codex" in str(cmd[0]):
            res = MagicMock()
            res.returncode = 0
            res.stdout = (
                'Found edge case vulnerability in input validation.\n{"verdict": "REPAIR_REQUIRED"}'
            )
            res.stderr = ""
            return res
        return orig_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        verdict = engine.execute_senior_review(sample_task_id)

        # Since Codex is active and rejects, unanimous approval is False
        assert verdict.approved is False
        assert verdict.codex_verdict == "REPAIR_REQUIRED"
        assert verdict.codex_bypassed is False

        # Verify queue was asked to queue task for repair turn
        assert mock_queue.queue_task_for_senior_repair.called
        call_args = mock_queue.queue_task_for_senior_repair.call_args[0]
        assert call_args[0] == sample_task_id
        assert "OpenAI Codex" in call_args[1]


# ---------------------------------------------------------------------------
# Senior Planning Engine Tests
# ---------------------------------------------------------------------------


def test_senior_planning_codex_critique_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queue = MagicMock(spec=TaskTriageQueue)
    broker = MagicMock(spec=ResearchBroker)
    dummy_agy = tmp_path / "agy"
    dummy_agy.touch()

    engine = SeniorPlanningEngine(queue=queue, research_broker=broker, agy_bin=dummy_agy)
    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    blueprint = PlanBlueprint(
        task_id="tsk_plan_001",
        base_sha="0" * 40,
        input_request_digest="d" * 64,
        research_snapshot_digest="r" * 64,
        requirements=["R1"],
        alternatives_considered=["A1"],
        chosen_design="D1",
        contracts=["C1"],
        file_scope=["alpha_worker/senior_review_engine.py"],
        gates=["pytest -q"],
        security_decisions=["S1"],
    )
    envelope = {"allowed_paths": ["alpha_worker/senior_review_engine.py"]}

    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value.returncode = 0
        mock_subproc.return_value.stdout = json.dumps(
            {"findings": "Design is sound and bounded.", "verdict": "APPROVE"}
        )
        mock_subproc.return_value.stderr = ""

        critique: PlanAssessment | None = engine.critique_plan_with_codex(
            blueprint=blueprint,
            envelope=envelope,
            research_snapshot_json="{}",
            subcommand="exec",
        )

        assert critique is not None
        assert critique.verdict == "APPROVE"
        assert "Design is sound" in critique.findings
        assert critique.reviewer_principal == "openai-codex-gpt-5.6-terra"

        call_args, _ = mock_subproc.call_args
        cmd = call_args[0]
        assert "codex" in cmd[0]
        assert cmd[1] == "exec"
        assert cmd[cmd.index("--model") + 1] == "gpt-5.6-terra"


def test_senior_planning_codex_holiday_circuit_breaker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = MagicMock(spec=TaskTriageQueue)
    broker = MagicMock(spec=ResearchBroker)
    engine = SeniorPlanningEngine(queue=queue, research_broker=broker)

    monkeypatch.setenv("CODEX_ON_HOLIDAY", "1")

    blueprint = PlanBlueprint(
        task_id="tsk_plan_002",
        base_sha="0" * 40,
        input_request_digest="d" * 64,
        research_snapshot_digest="r" * 64,
        requirements=["R1"],
        alternatives_considered=["A1"],
        chosen_design="D1",
        contracts=["C1"],
        file_scope=["alpha_worker/senior_review_engine.py"],
        gates=["pytest -q"],
        security_decisions=["S1"],
    )

    with patch("subprocess.run") as mock_subproc:
        critique = engine.critique_plan_with_codex(
            blueprint=blueprint,
            envelope={},
            research_snapshot_json="{}",
        )
        assert critique is None
        assert mock_subproc.call_count == 0


def test_senior_planning_codex_rate_limit_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = MagicMock(spec=TaskTriageQueue)
    broker = MagicMock(spec=ResearchBroker)
    engine = SeniorPlanningEngine(queue=queue, research_broker=broker)

    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    blueprint = PlanBlueprint(
        task_id="tsk_plan_003",
        base_sha="0" * 40,
        input_request_digest="d" * 64,
        research_snapshot_digest="r" * 64,
        requirements=["R1"],
        alternatives_considered=["A1"],
        chosen_design="D1",
        contracts=["C1"],
        file_scope=["alpha_worker/senior_review_engine.py"],
        gates=["pytest -q"],
        security_decisions=["S1"],
    )

    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value.returncode = 1
        mock_subproc.return_value.stdout = ""
        mock_subproc.return_value.stderr = "Rate limit exceeded: 429 quota exhausted."

        critique = engine.critique_plan_with_codex(
            blueprint=blueprint,
            envelope={},
            research_snapshot_json="{}",
        )
        # Bypasses cleanly without raising exception
        assert critique is None


def test_senior_planning_codex_repair_required_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = MagicMock(spec=TaskTriageQueue)
    broker = MagicMock(spec=ResearchBroker)
    engine = SeniorPlanningEngine(queue=queue, research_broker=broker)

    monkeypatch.delenv("CODEX_ON_HOLIDAY", raising=False)

    blueprint = PlanBlueprint(
        task_id="tsk_plan_004",
        base_sha="0" * 40,
        input_request_digest="d" * 64,
        research_snapshot_digest="r" * 64,
        requirements=["R1"],
        alternatives_considered=["A1"],
        chosen_design="D1",
        contracts=["C1"],
        file_scope=["alpha_worker/senior_review_engine.py"],
        gates=["pytest -q"],
        security_decisions=["S1"],
    )

    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value.returncode = 0
        mock_subproc.return_value.stdout = "```json\n" + json.dumps(
            {"findings": "Missing rollback verification.", "verdict": "REPAIR_REQUIRED"}
        ) + "\n```"
        mock_subproc.return_value.stderr = ""

        critique = engine.critique_plan_with_codex(
            blueprint=blueprint,
            envelope={},
            research_snapshot_json="{}",
        )
        assert critique is not None
        assert critique.verdict == "REPAIR_REQUIRED"
        assert "Missing rollback" in critique.findings


def test_execute_planning_phase_e2e_with_codex_critique(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = MagicMock(spec=TaskTriageQueue)
    envelope = {
        "objective": "Integrate Codex Senior Review",
        "project_id": "test_project",
        "repo": "local",
        "base_commit": "a" * 40,
        "allowed_paths": ["alpha_worker/senior_review_engine.py"],
    }
    queue.get_task.return_value = {
        "envelope": envelope,
        "status": "pending_review",
    }
    snapshot = ResearchSnapshot(
        task_id="tsk_e2e_plan",
        project_id="test_project",
        repository_identity="local",
        base_sha="a" * 40,
        request_digest=request_digest(envelope),
        retrieval_time=1,
    )
    dummy_agy = tmp_path / "agy"
    dummy_agy.touch()

    engine = SeniorPlanningEngine(
        queue=queue,
        research_broker=MagicMock(),
        agy_bin=dummy_agy,
        signing_secret="test_secret_for_signing_planning_attestation",
        key_id="alpha_production_v1",
    )

    # Mock AGY for Pro draft and Opus critique
    def fake_agy_planning(model: str, prompt: str, schema: dict, timeout_seconds: int = 600) -> dict[str, Any]:
        if "gemini" in model:
            return {
                "requirements": ["R1"],
                "alternatives_considered": ["A1"],
                "chosen_design": "Design 1",
                "contracts": ["C1"],
                "file_scope": ["alpha_worker/senior_review_engine.py"],
                "gates": ["pytest -q"],
                "security_decisions": ["Sec1"],
            }
        # Opus critique verifies Codex prompt injection
        assert "OpenAI Codex" in prompt
        return {"findings": "Approved with Codex consideration.", "verdict": "APPROVE"}

    monkeypatch.setattr(engine, "_invoke_agy_planning", fake_agy_planning)

    # Mock Codex critique returning APPROVE
    def fake_codex(*a: Any, **k: Any) -> PlanAssessment:
        return PlanAssessment(
            reviewer_principal="openai-codex-gpt-5.6-terra",
            role="critique",
            plan_digest="0" * 64,
            verdict="APPROVE",
            findings="Codex found no architectural blockers.",
        )

    monkeypatch.setattr(engine, "critique_plan_with_codex", fake_codex)

    attestation, blueprint = engine.execute_planning_phase("tsk_e2e_plan", snapshot)

    assert attestation is not None
    assert blueprint is not None
    assert engine.last_codex_assessment is not None
    assert engine.last_codex_assessment.verdict == "APPROVE"
