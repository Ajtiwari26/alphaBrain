"""Unit tests for isolated Antigravity project conversations."""

import json

import pytest

from alpha_protocol import TaskEnvelope
from alpha_worker.adapters.antigravity_live import (
    COMPLETION_TOKEN,
    QA_EVIDENCE_TOKEN,
    SDLC_SKILL_NAME,
    AntigravityLiveBridge,
)


def make_task(project_id: str = "prj_calculator", session_id: str | None = None) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="tsk_calculator_01",
        project_id=project_id,
        repo="/tmp/alpha-calculator-repo",
        objective="Build calculator",
        detailed_instructions="Create a scientific calculator.",
        allowed_paths=["."],
        allowed_tools=["code-review-graph"],
        session_id=session_id,
    )


@pytest.mark.asyncio
async def test_project_chat_is_registered_once_and_never_reused_cross_project(tmp_path):
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path / "store"
    bridge.hub_conversation_dir = tmp_path / "hub"
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    first_id, first_new = await bridge._get_or_create_project_conversation(
        make_task(session_id="00000000-0000-0000-0000-000000000001"), worktree
    )
    second_id, second_new = await bridge._get_or_create_project_conversation(make_task(), worktree)
    other_id, other_new = await bridge._get_or_create_project_conversation(
        make_task("prj_other", session_id="00000000-0000-0000-0000-000000000002"), worktree
    )

    assert first_new is False
    assert second_new is False
    assert other_new is False
    assert first_id == second_id
    assert other_id != first_id


@pytest.mark.asyncio
async def test_missing_project_chat_requests_internal_creation(tmp_path):
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path / "store"
    bridge.hub_conversation_dir = tmp_path / "hub"
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    conversation_id, is_new = await bridge._get_or_create_project_conversation(
        make_task(), worktree
    )

    assert conversation_id is None
    assert is_new is True


@pytest.mark.asyncio
async def test_completion_requires_code_review_graph_calls(tmp_path):
    bridge = AntigravityLiveBridge()
    bridge.brain_dirs = (tmp_path,)
    conversation_id = "00000000-0000-0000-0000-000000000001"
    transcript = tmp_path / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        "\n".join(
            [
                json.dumps({"tool_calls": [{"name": "build_or_update_graph_tool"}]}),
                json.dumps({"tool_calls": [{"name": "get_review_context_tool"}]}),
                json.dumps({"source": "MODEL", "content": COMPLETION_TOKEN}),
            ]
        )
        + "\n"
    )

    result = await bridge._wait_for_completion(conversation_id, after_line=0, timeout_seconds=1)

    assert result.completed is True
    assert result.blocked_reason is None
    assert set(result.tool_names) == {
        "build_or_update_graph_tool",
        "get_review_context_tool",
    }


def test_task_prompt_requires_code_review_graph_protocol(tmp_path):
    bridge = AntigravityLiveBridge()
    prompt = bridge._build_task_prompt(make_task(), tmp_path, is_new_project=True)

    assert "build_or_update_graph_tool" in prompt
    assert "get_review_context_tool" in prompt
    assert SDLC_SKILL_NAME in prompt
    assert QA_EVIDENCE_TOKEN in prompt
    assert COMPLETION_TOKEN in prompt


def test_qa_evidence_requires_expected_project_and_gate():
    valid = (
        QA_EVIDENCE_TOKEN
        + '{"skill":"multi-agent-sdlc","project_id":"prj_calculator",'
        + '"testscript_root":"testscript","passed_gates":["unit_test"],'
        + '"security_review":{"executed":true}}'
    )
    evidence, error = AntigravityLiveBridge._parse_qa_evidence(
        valid, ("unit_test",), "prj_calculator"
    )
    assert error is None
    assert evidence is not None

    _, missing_gate = AntigravityLiveBridge._parse_qa_evidence(
        valid, ("browser_smoke",), "prj_calculator"
    )
    assert missing_gate == "QA evidence missing required gates: browser_smoke"

    _, wrong_project = AntigravityLiveBridge._parse_qa_evidence(valid, ("unit_test",), "prj_other")
    assert wrong_project == "QA evidence project_id does not match dispatched task"
