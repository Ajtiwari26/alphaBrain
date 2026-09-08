from unittest.mock import MagicMock, patch

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_worker.senior_review_engine import SeniorReviewEngine


def test_parse_verdict_line_variations(tmp_path):
    queue = MagicMock(spec=TaskTriageQueue)
    engine = SeniorReviewEngine(queue=queue)

    # 1. Plain one-line JSON on the last line
    out1 = 'Great work.\n{"verdict": "APPROVE"}'
    assert (
        engine.parse_verdict_line(out1, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "APPROVE"
    )

    # 2. Valid Opus verdict on the last line
    out2 = 'Architecture compliant.\n{"verdict": "FINAL_APPROVAL"}'
    assert (
        engine.parse_verdict_line(out2, ["FINAL_APPROVAL", "REJECT"], "REJECT") == "FINAL_APPROVAL"
    )

    # 3. Wrong enum falls back to default
    assert engine.parse_verdict_line(out1, ["FINAL_APPROVAL", "REJECT"], "REJECT") == "REJECT"

    # 4. Non-last-line JSON falls back to default
    out4 = '{"verdict": "APPROVE"}\nFinal thought: not ready'
    assert (
        engine.parse_verdict_line(out4, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 5. Unknown verdict falls back to default
    out5 = '{"verdict": "MAYBE"}'
    assert (
        engine.parse_verdict_line(out5, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )


def test_invoke_agy_command_flags(tmp_path):
    queue = MagicMock(spec=TaskTriageQueue)
    engine = SeniorReviewEngine(queue=queue)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            '{"status": "SUCCESS", "response": "{\\"verdict\\": \\"APPROVE\\"}"}'
        )
        mock_run.return_value.stderr = ""

        engine._invoke_agy(
            model="claude-opus-4-6-thinking",
            prompt="Test prompt",
            schema_path=str(tmp_path / "schema.json"),
        )

        assert mock_run.called
        call_args, call_kwargs = mock_run.call_args
        cmd = call_args[0]

        # Verify critical flags
        assert "--dangerously-skip-permissions" in cmd
        assert "--input-format" in cmd
        assert "text" in cmd
        assert call_kwargs.get("input") == "Test prompt"
