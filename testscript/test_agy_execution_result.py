"""
testscript/test_agy_execution_result.py
Deterministic unit tests for Antigravity typed attempt outcome structures,
status transitions, and execution result validation.
"""

import json
from pathlib import Path

from alpha_worker.adapters.antigravity_live import (
    BLOCKED_TOKEN,
    COMPLETION_TOKEN,
    QA_EVIDENCE_TOKEN,
    SDLC_SKILL_NAME,
    AGYAttemptStatus,
    AntigravityAttemptOutcome,
    AntigravityDispatch,
    evaluate_agy_execution_outcome,
)

CONVERSATION_ID = "11111111-2222-3333-4444-555555555555"
PROJECT_ID = "prj_test_exec"


def make_qa_evidence(
    project_id: str = PROJECT_ID,
    passed_gates: list[str] | None = None,
    security_passed: bool = True,
    include_audit: bool = False,
    include_browser: bool = False,
) -> str:
    manifest = {
        "skill": SDLC_SKILL_NAME,
        "project_id": project_id,
        "testscript_root": "testscript",
        "passed_gates": passed_gates if passed_gates is not None else ["unit_test", "lint"],
        "security_review": {
            "executed": security_passed,
            "status": "passed" if security_passed else "failed",
        },
    }
    if include_browser:
        manifest["browser_e2e"] = {"executed": True, "result": "passed"}
    if include_audit:
        manifest["qa_audit"] = {
            "executed": True,
            "result": "passed",
            "defects_found": 0,
            "defects_fixed": 0,
            "browser_evidence": ["docs/qa/browser.json"],
        }
    return f"{QA_EVIDENCE_TOKEN}{json.dumps(manifest)}\n{COMPLETION_TOKEN}"


def make_valid_events(response_text: str | None = None) -> list[dict[str, object]]:
    return [
        {"event": "init", "conversation_id": CONVERSATION_ID},
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "build_or_update_graph_tool",
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_info": {"name": "get_review_context_tool"},
            },
        },
        {
            "event": "result",
            "result": {
                "conversation_id": CONVERSATION_ID,
                "status": "SUCCESS",
                "response": response_text or make_qa_evidence(),
            },
        },
    ]


def test_successful_execution_outcome():
    events = make_valid_events()
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        pid=12345,
        exit_code=0,
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
        changed_files=("src/app.py", "testscript/test_app.py"),
        diff_summary="2 files changed, 50 insertions(+)",
    )

    assert outcome.status == AGYAttemptStatus.SUCCEEDED
    assert outcome.completed is True
    assert outcome.exit_code == 0
    assert outcome.pid == 12345
    assert outcome.model == "gemini-3.1-pro"
    assert outcome.conversation_id == CONVERSATION_ID
    assert outcome.blocked_reason is None
    assert outcome.blockers == ()
    assert outcome.changed_files == ("src/app.py", "testscript/test_app.py")
    assert outcome.diff_summary == "2 files changed, 50 insertions(+)"
    assert outcome.qa_evidence is not None
    assert outcome.qa_evidence["skill"] == SDLC_SKILL_NAME
    assert set(outcome.tool_names) == {"build_or_update_graph_tool", "get_review_context_tool"}


def test_nonzero_exit_code_refuses_success():
    events = make_valid_events()
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        pid=12345,
        exit_code=1,
        events=events,
        stderr="fatal error in AGY CLI runner",
        expected_qa_gates=("unit_test",),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert outcome.exit_code == 1
    assert "fatal error" in (outcome.blocked_reason or "")
    assert len(outcome.blockers) > 0


def test_timeout_exit_code_and_status():
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        pid=12345,
        exit_code=-1,
        stderr="AGY CLI timed out after 300s",
        expected_qa_gates=("unit_test",),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.TIMED_OUT
    assert outcome.completed is False
    assert outcome.exit_code == -1
    assert "timed out" in (outcome.blocked_reason or "")

    raw_outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        raw_status=AGYAttemptStatus.TIMED_OUT,
        stderr="Execution timeout reached",
    )
    assert raw_outcome.status == AGYAttemptStatus.TIMED_OUT
    assert raw_outcome.completed is False


def test_cancelled_status_refuses_success():
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        raw_status=AGYAttemptStatus.CANCELLED,
        stderr="User cancelled task execution",
    )

    assert outcome.status == AGYAttemptStatus.CANCELLED
    assert outcome.completed is False
    assert "cancelled" in (outcome.blocked_reason or "").lower()


def test_rate_limited_detection():
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        exit_code=0,
        stderr="Error: 429 RESOURCE_EXHAUSTED Rate limit exceeded for model",
    )

    assert outcome.status == AGYAttemptStatus.RATE_LIMITED
    assert outcome.completed is False
    assert "Rate limit" in (outcome.blocked_reason or "")


def test_blocked_token_refuses_success():
    blocked_response = (
        f"Cannot proceed with external call\n{BLOCKED_TOKEN}: missing API key for payment gateway"
    )
    events = make_valid_events(response_text=blocked_response)
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test",),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.BLOCKED
    assert outcome.completed is False
    assert "missing API key" in (outcome.blocked_reason or "")


def test_quiet_period_or_missing_result_refuses_success():
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=[{"event": "init", "conversation_id": CONVERSATION_ID}],
        expected_qa_gates=("unit_test",),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert (
        "failed" in (outcome.blocked_reason or "").lower()
        or "missing" in (outcome.blocked_reason or "").lower()
    )


def test_done_text_without_qa_manifest_refuses_success():
    events = make_valid_events(response_text="All tasks are done! Completed successfully.")
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test",),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "ALPHA_BRAIN_TASK_DONE" in (outcome.blocked_reason or "")


def test_missing_required_review_tools_refuses_success():
    events = [
        {"event": "init", "conversation_id": CONVERSATION_ID},
        {
            "event": "step_update",
            "step_update": {"step_type": "tool", "tool_name": "edit_file"},
        },
        {
            "event": "result",
            "result": {
                "conversation_id": CONVERSATION_ID,
                "status": "SUCCESS",
                "response": make_qa_evidence(),
            },
        },
    ]
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "code-review graph" in (outcome.blocked_reason or "")


def test_mcp_review_tools_accepted():
    events = [
        {"event": "init", "conversation_id": CONVERSATION_ID},
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "call_mcp_tool",
                "tool_info": {
                    "parameters": {
                        "ServerName": "code-review-graph",
                        "ToolName": "build_or_update_graph_tool",
                    }
                },
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "call_mcp_tool",
                "tool_info": {
                    "parameters": {
                        "ServerName": "code-review-graph",
                        "ToolName": "get_review_context_tool",
                    }
                },
            },
        },
        {
            "event": "result",
            "result": {
                "conversation_id": CONVERSATION_ID,
                "status": "SUCCESS",
                "response": make_qa_evidence(),
            },
        },
    ]
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.SUCCEEDED
    assert outcome.completed is True
    assert "code-review-graph/build_or_update_graph_tool" in outcome.tool_names
    assert "code-review-graph/get_review_context_tool" in outcome.tool_names


def test_missing_required_gate_in_qa_evidence_refuses_success():
    events = make_valid_events(response_text=make_qa_evidence(passed_gates=["unit_test"]))
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint", "build"),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "missing required gates" in (outcome.blocked_reason or "")


def test_unexecuted_security_review_in_qa_evidence_refuses_success():
    events = make_valid_events(response_text=make_qa_evidence(security_passed=False))
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "security review" in (outcome.blocked_reason or "").lower()


def test_browser_smoke_without_e2e_proof_refuses_success():
    events = make_valid_events(
        response_text=make_qa_evidence(
            passed_gates=["unit_test", "browser_smoke"], include_browser=False
        )
    )
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "browser_smoke"),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "browser E2E" in (outcome.blocked_reason or "")


def test_qa_audit_required_and_missing_refuses_success():
    events = make_valid_events(response_text=make_qa_evidence(include_audit=False))
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
        require_qa_audit=True,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "independent audit" in (outcome.blocked_reason or "")


def test_project_id_mismatch_in_qa_evidence_refuses_success():
    events = make_valid_events(response_text=make_qa_evidence(project_id="prj_different"))
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )

    assert outcome.status == AGYAttemptStatus.FAILED
    assert outcome.completed is False
    assert "project_id" in (outcome.blocked_reason or "")


def test_antigravity_attempt_outcome_field_types_and_dispatch_compatibility():
    outcome = AntigravityAttemptOutcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        pid=9999,
        exit_code=0,
        status=AGYAttemptStatus.SUCCEEDED,
        changed_files=("a.py", "b.py"),
        diff_summary="2 files changed",
        artifacts=("art1.json",),
        blockers=(),
        gate_evidence={"passed": True},
        tool_names=("tool_a", "tool_b"),
        final_message="done",
        transcript_path=Path("/tmp/transcript.json"),
        qa_evidence={"skill": SDLC_SKILL_NAME},
        blocked_reason=None,
    )

    assert outcome.completed is True
    assert outcome.status == AGYAttemptStatus.SUCCEEDED
    assert isinstance(outcome.changed_files, tuple)
    assert isinstance(outcome.artifacts, tuple)
    assert isinstance(outcome.blockers, tuple)
    assert isinstance(outcome.tool_names, tuple)

    dispatch = AntigravityDispatch(
        conversation_id=outcome.conversation_id,
        completed=outcome.completed,
        blocked_reason=outcome.blocked_reason,
        tool_names=outcome.tool_names,
        final_message=outcome.final_message,
        transcript_path=outcome.transcript_path,
        qa_evidence=outcome.qa_evidence,
        pid=outcome.pid,
        exit_code=outcome.exit_code,
        model=outcome.model,
        status=outcome.status,
        changed_files=outcome.changed_files,
        diff_summary=outcome.diff_summary,
        artifacts=outcome.artifacts,
        blockers=outcome.blockers,
        gate_evidence=outcome.gate_evidence,
    )

    assert dispatch.completed is True
    assert dispatch.status == AGYAttemptStatus.SUCCEEDED
    assert dispatch.pid == 9999
    assert dispatch.model == "gemini-3.1-pro"


def test_plan_mentions_both_markers_plus_valid_manifest_plus_final_done_succeeds():
    manifest_str = json.dumps(
        {
            "skill": SDLC_SKILL_NAME,
            "project_id": PROJECT_ID,
            "testscript_root": "testscript",
            "passed_gates": ["unit_test", "lint"],
            "security_review": {"executed": True, "status": "passed"},
        }
    )

    response_text = f"""
I plan to return {COMPLETION_TOKEN} or {BLOCKED_TOKEN}.
Let's finish this.
{QA_EVIDENCE_TOKEN}{manifest_str}
{COMPLETION_TOKEN}
"""
    events = make_valid_events(response_text=response_text)
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )
    assert outcome.completed is True
    assert outcome.status == AGYAttemptStatus.SUCCEEDED


def test_final_blocked_reason_blocks():
    manifest_str = json.dumps(
        {
            "skill": SDLC_SKILL_NAME,
            "project_id": PROJECT_ID,
            "testscript_root": "testscript",
            "passed_gates": ["unit_test", "lint"],
            "security_review": {"executed": True, "status": "passed"},
        }
    )

    response_text = f"""
{QA_EVIDENCE_TOKEN}{manifest_str}
{BLOCKED_TOKEN}: Something went wrong
"""
    events = make_valid_events(response_text=response_text)
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )
    assert outcome.completed is False
    assert outcome.status == AGYAttemptStatus.BLOCKED
    assert outcome.blocked_reason == "Something went wrong"


def test_prose_only_mention_fails():
    response_text = f"""
We are now {COMPLETION_TOKEN} and ready.
Wait, no we are {BLOCKED_TOKEN}.
"""
    events = make_valid_events(response_text=response_text)
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )
    assert outcome.completed is False
    assert outcome.status == AGYAttemptStatus.FAILED
    assert "omitted terminal" in (outcome.blocked_reason or "")


def test_earlier_blocked_then_final_done_succeeds():
    manifest_str = json.dumps(
        {
            "skill": SDLC_SKILL_NAME,
            "project_id": PROJECT_ID,
            "testscript_root": "testscript",
            "passed_gates": ["unit_test", "lint"],
            "security_review": {"executed": True, "status": "passed"},
        }
    )

    response_text = f"""
{BLOCKED_TOKEN}
Wait, no I fixed it.
{QA_EVIDENCE_TOKEN}{manifest_str}
{COMPLETION_TOKEN}
"""
    events = make_valid_events(response_text=response_text)
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )
    assert outcome.completed is True
    assert outcome.status == AGYAttemptStatus.SUCCEEDED


def test_earlier_done_then_final_blocked_blocks():
    manifest_str = json.dumps(
        {
            "skill": SDLC_SKILL_NAME,
            "project_id": PROJECT_ID,
            "testscript_root": "testscript",
            "passed_gates": ["unit_test", "lint"],
            "security_review": {"executed": True, "status": "passed"},
        }
    )

    response_text = f"""
{QA_EVIDENCE_TOKEN}{manifest_str}
{COMPLETION_TOKEN}
Actually no.
{BLOCKED_TOKEN}: found a new issue
"""
    events = make_valid_events(response_text=response_text)
    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )
    assert outcome.completed is False
    assert outcome.status == AGYAttemptStatus.BLOCKED
    assert outcome.blocked_reason == "found a new issue"


def test_stream_bookkeeping_after_final_result_cannot_override_result_payload():
    manifest_str = json.dumps(
        {
            "skill": SDLC_SKILL_NAME,
            "project_id": PROJECT_ID,
            "testscript_root": "testscript",
            "passed_gates": ["unit_test", "lint"],
            "security_review": {"executed": True, "status": "passed"},
        }
    )

    response_text = f"""
{QA_EVIDENCE_TOKEN}{manifest_str}
{COMPLETION_TOKEN}
"""

    events = make_valid_events(response_text=response_text)
    events.append(
        {
            "event": "step_update",
            "step_update": {"step_type": "agent_response", "text_delta": f"Oops, {BLOCKED_TOKEN}"},
        }
    )

    outcome = evaluate_agy_execution_outcome(
        conversation_id=CONVERSATION_ID,
        model="gemini-3.1-pro",
        events=events,
        expected_qa_gates=("unit_test", "lint"),
        expected_project_id=PROJECT_ID,
    )
    assert outcome.completed is True
    assert outcome.status == AGYAttemptStatus.SUCCEEDED
