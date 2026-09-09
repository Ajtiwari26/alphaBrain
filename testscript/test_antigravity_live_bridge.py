"""Tests for official AGY CLI project-scoped task bridge."""

import json
from unittest.mock import MagicMock

import pytest

from alpha_core.config import settings
from alpha_protocol import AcceptancePlan, GateCommand, GateType, TaskEnvelope
from alpha_worker.adapters.antigravity_live import (
    BLOCKED_TOKEN,
    COMPLETION_TOKEN,
    QA_EVIDENCE_TOKEN,
    SDLC_SKILL_NAME,
    AntigravityLiveBridge,
)

CONVERSATION_ID = "00000000-0000-0000-0000-000000000001"


def make_task(
    project_id: str = "prj_calculator",
    session_id: str | None = None,
    repo: str = "/tmp/alpha-calculator-repo",
    objective: str = "objective",
    task_id: str = "tsk_calculator_01",
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        project_id=project_id,
        repo=repo,
        objective=objective,
        detailed_instructions="Create a scientific calculator.",
        allowed_paths=["."],
        allowed_tools=["code-review-graph"],
        session_id=session_id,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["-q", "calculator_contract_test.py"],
                )
            ],
        ),
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )


def valid_response(include_audit: bool = False) -> str:
    evidence = {
        "skill": SDLC_SKILL_NAME,
        "project_id": "prj_calculator",
        "testscript_root": "testscript",
        "passed_gates": ["unit_test"],
        "security_review": {"executed": True},
    }
    if include_audit:
        evidence["qa_audit"] = {
            "executed": True,
            "result": "passed",
            "defects_found": 1,
            "defects_fixed": 1,
            "browser_evidence": ["docs/qa/evidence/browser.json"],
        }
    return f"{QA_EVIDENCE_TOKEN}{json.dumps(evidence)}\n{COMPLETION_TOKEN}"


def valid_events(response: str | None = None) -> list[dict[str, object]]:
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
                "response": response or valid_response(),
            },
        },
    ]


def test_project_chat_is_registered_once_and_never_reused_cross_project(tmp_path):
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path / "store"

    first_id, first_new = bridge._get_project_conversation(make_task(session_id=CONVERSATION_ID))
    second_id, second_new = bridge._get_project_conversation(make_task())
    other_id, other_new = bridge._get_project_conversation(
        make_task(
            "prj_other", session_id="00000000-0000-0000-0000-000000000002", task_id="tsk_other_01"
        )
    )

    assert first_new is False
    assert second_new is False
    assert other_new is False
    assert first_id == second_id
    assert other_id != first_id


def test_missing_project_chat_requests_official_new_project(tmp_path):
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path / "store"

    conversation_id, is_new = bridge._get_project_conversation(make_task())

    assert conversation_id is None
    assert is_new is True


def test_configured_chat_is_limited_to_alphabrain_repository(tmp_path, monkeypatch):
    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path / "store"
    alpha_repo = tmp_path / "alphaBrain"
    alpha_repo.mkdir()
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", alpha_repo)
    monkeypatch.setattr(settings, "ALPHA_BRAIN_ANTIGRAVITY_CONVERSATION_ID", CONVERSATION_ID)

    alpha_id, alpha_new = bridge._get_project_conversation(
        make_task(project_id="prj_alpha", repo=str(alpha_repo))
    )
    client_id, client_new = bridge._get_project_conversation(
        make_task(project_id="prj_client", repo=str(tmp_path / "client"))
    )

    assert alpha_id == CONVERSATION_ID and alpha_new is False
    assert client_id is None and client_new is True


def test_agy_result_requires_review_tools_and_qa_evidence():
    raw = {"returncode": 0, "events": valid_events(), "stderr": ""}

    result = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        forbid_external_dependencies=True,
    )

    assert result.completed is True
    assert result.blocked_reason is None
    assert set(result.tool_names) == {
        "build_or_update_graph_tool",
        "get_review_context_tool",
    }
    assert result.qa_evidence is not None

    generic_mcp_events = valid_events()
    generic_mcp_events[1]["step_update"] = {
        "step_type": "tool",
        "tool_name": "call_mcp_tool",
        "tool_info": {
            "parameters": {
                "ServerName": "code-review-graph",
                "ToolName": "build_or_update_graph_tool",
            }
        },
    }
    generic_mcp_events[2]["step_update"] = {
        "step_type": "tool",
        "tool_name": "call_mcp_tool",
        "tool_info": {
            "parameters": {
                "ServerName": "code-review-graph",
                "ToolName": "get_review_context_tool",
            }
        },
    }
    generic_mcp = AntigravityLiveBridge._parse_agy_result(
        {"returncode": 0, "events": generic_mcp_events, "stderr": ""},
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
    )
    assert generic_mcp.completed is True
    assert "code-review-graph/build_or_update_graph_tool" in generic_mcp.tool_names

    missing_tool_events = valid_events()
    missing_tool_events.pop(2)
    raw["events"] = missing_tool_events
    missing_tool = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        forbid_external_dependencies=True,
    )
    assert missing_tool.completed is False
    assert "get_review_context_tool" in (missing_tool.blocked_reason or "")


def test_audit_result_requires_audit_evidence():
    raw = {"returncode": 0, "events": valid_events(valid_response(True)), "stderr": ""}
    audited = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        require_qa_audit=True,
    )
    assert audited.completed is True

    raw["events"] = valid_events()
    missing_audit = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        require_qa_audit=True,
    )
    assert missing_audit.completed is False
    assert missing_audit.blocked_reason == "QA evidence missing passed independent audit"


def test_legacy_agy_security_and_browser_summary_evidence_is_accepted():
    response = (
        f"{QA_EVIDENCE_TOKEN}"
        f"{json.dumps({'skill': SDLC_SKILL_NAME, 'project_id': 'prj_calculator', 'testscript_root': 'testscript', 'passed_gates': ['unit_test', 'browser_smoke'], 'security_review': {'status': 'PASSED'}, 'browser_e2e_tests': {'total': 32, 'passed': 32}})}"
        f"\n{COMPLETION_TOKEN}"
    )
    result = AntigravityLiveBridge._parse_agy_result(
        {"returncode": 0, "events": valid_events(response), "stderr": ""},
        expected_qa_gates=("unit_test", "browser_smoke"),
        expected_project_id="prj_calculator",
    )

    assert result.completed is True


def test_agy_result_fails_closed_on_missing_completion_or_cli_error():
    missing_completion = AntigravityLiveBridge._parse_agy_result(
        {"returncode": 0, "events": valid_events("work complete"), "stderr": ""},
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
    )
    assert missing_completion.completed is False
    assert COMPLETION_TOKEN in (missing_completion.blocked_reason or "")

    cli_error = AntigravityLiveBridge._parse_agy_result(
        {
            "returncode": 1,
            "events": [
                {
                    "event": "result",
                    "result": {
                        "conversation_id": CONVERSATION_ID,
                        "status": "ERROR",
                        "error": "invalid model",
                    },
                }
            ],
            "stderr": "invalid model",
        },
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
    )
    assert cli_error.completed is False
    assert cli_error.blocked_reason == "invalid model"


def test_task_prompt_contains_execution_contract(tmp_path):
    prompt = AntigravityLiveBridge()._build_task_prompt(make_task(), tmp_path, is_new_project=True)

    # Version and immutable fields
    assert "AlphaBrain Junior Execution Contract (Version 1)" in prompt
    assert "Task ID:" in prompt
    assert "Project ID:" in prompt
    assert "Worktree:" in prompt
    assert "Base commit:" in prompt
    assert "Allowed paths:" in prompt
    assert "Allowed tools:" in prompt
    assert "Risk class:" in prompt
    assert "Accepted gate commands:" in prompt

    # Failure and completion protocol
    assert COMPLETION_TOKEN in prompt
    assert BLOCKED_TOKEN in prompt
    assert "SUCCESS: ONLY after every gate passes" in prompt
    assert "FAILURE: On blocked or failing gate" in prompt

    # Manifest contract
    assert QA_EVIDENCE_TOKEN in prompt
    assert '"contract_version": 1' in prompt
    # Exact regression test: no double colon or newline between token and JSON
    assert f'{QA_EVIDENCE_TOKEN}{{"contract_version": 1' in prompt
    assert f"{QA_EVIDENCE_TOKEN}:" not in prompt

    # Anti-patterns
    assert "No claiming tests pass without actual captured command output" in prompt
    assert "No silent permission denial" in prompt
    assert "No self-approval, no deployments" in prompt
    assert "No roadmap changes or broader refactoring" in prompt
    assert "No invented fallback models" in prompt


def test_audit_prompt_includes_exact_declared_commands(tmp_path):
    prompt = AntigravityLiveBridge()._build_qa_audit_prompt(make_task(), tmp_path)

    assert "pytest -q calculator_contract_test.py" in prompt
    assert "source-control hygiene" in prompt


def test_compliance_repair_prompt_names_exact_missing_proof(tmp_path):
    dispatch = AntigravityLiveBridge._parse_agy_result(
        {"returncode": 0, "events": valid_events(), "stderr": ""},
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
    )
    prompt = AntigravityLiveBridge()._build_compliance_repair_prompt(
        make_task(), tmp_path, dispatch
    )

    assert "get_review_context_tool" in prompt


def test_bounded_repair_combines_required_review_proof():
    first_events = valid_events()
    first_events.pop(2)
    repair_events = valid_events()
    repair_events.pop(1)
    combined = AntigravityLiveBridge._combine_turn_evidence(
        {"returncode": 0, "events": first_events, "stderr": ""},
        {"returncode": 0, "events": repair_events, "stderr": ""},
    )

    result = AntigravityLiveBridge._parse_agy_result(
        combined,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
    )
    assert result.completed is True


@pytest.mark.asyncio
async def test_run_agy_includes_model_and_effort(monkeypatch, tmp_path):
    import subprocess

    from alpha_core.config import settings
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    monkeypatch.setattr(settings, "ANTIGRAVITY_MODEL", "gemini-3.1-pro")
    monkeypatch.setattr(settings, "ANTIGRAVITY_EFFORT", "high")

    mock_process = MagicMock()
    mock_process.poll.return_value = 0

    # We need an explicit function to capture arguments because we want to assert the first arg to Popen
    captured_args = []

    def fake_popen(args, **kwargs):
        captured_args.extend(args)
        # To avoid file reading errors in _run_agy
        return mock_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    # Also need to mock the file reading so it doesn't crash on reading empty files.
    # Actually wait, _run_agy opens files in TemporaryDirectory and reads them at the end.
    # So if they are empty, json.loads might fail. Let's patch _run_agy to return early or just let it fail after capturing.

    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path

    try:
        await bridge._run_agy(
            prompt="Hello",
            worktree_path=tmp_path,
            conversation_id="conv-1",
            is_new_project=False,
            timeout_seconds=30,
        )
    except Exception:
        pass  # We only care about the captured arguments before it attempts parsing

    assert "--model" in captured_args
    assert captured_args[captured_args.index("--model") + 1] == "gemini-3.1-pro"

    assert "--effort" in captured_args
    assert captured_args[captured_args.index("--effort") + 1] == "high"


@pytest.mark.asyncio
async def test_run_agy_injects_safety_hook(monkeypatch, tmp_path):
    import json
    import subprocess

    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    mock_process = MagicMock()
    mock_process.poll.return_value = 0
    captured_args = []

    def fake_popen(args, **kwargs):
        captured_args.extend(args)
        return mock_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    bridge = AntigravityLiveBridge()
    bridge.session_store_dir = tmp_path

    try:
        await bridge._run_agy(
            prompt="Hello",
            worktree_path=tmp_path,
            conversation_id="conv-1",
            is_new_project=False,
            timeout_seconds=30,
        )
    except Exception:
        pass

    # Verify the hook was injected
    hooks_file = tmp_path / ".agents" / "hooks.json"
    assert hooks_file.exists()

    hooks_config = json.loads(hooks_file.read_text())
    hook_cmd = hooks_config["worktree-safety-gate"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "ALPHA_WORKTREE_PATH=" in hook_cmd
    assert "safety_hook.py" in hook_cmd


def test_valid_version_1_manifest_is_accepted():
    manifest_str = 'ALPHA_BRAIN_QA_EVIDENCE:{"contract_version": 1, "skill": "multi-agent-sdlc", "testscript_root": "testscript", "project_id": "prj_calculator", "task_id": "task_1", "executed_commands": [{"command": "pytest", "exit_code": 0, "summary": "ok"}], "required_gates": ["unit_test"], "passed_gates": ["unit_test"], "review_calls": 2, "security_review": {"executed": true}, "artifacts": [], "blockers": []}'
    response = f"{manifest_str}\n{COMPLETION_TOKEN}"
    raw = {"returncode": 0, "events": valid_events(response), "stderr": ""}
    result = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        forbid_external_dependencies=True,
    )
    assert result.completed is True


def test_agy_result_fails_closed_on_unauthorized_commands():
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    events = valid_events()
    events.insert(
        0,
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "run_command",
                "tool_info": {"parameters": {"CommandLine": "npm install playwright"}},
            },
        },
    )

    raw = {"returncode": 0, "events": events, "stderr": ""}
    result = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        forbid_external_dependencies=True,
    )
    assert result.completed is False
    assert "Forbidden command execution detected" in (result.blocked_reason or "")
    assert "npm install" in (result.blocked_reason or "")


def test_dependency_free_prompt_injection(tmp_path):
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    task = make_task(objective="dependency-free task")
    prompt = AntigravityLiveBridge()._build_task_prompt(task, tmp_path, is_new_project=True)
    assert "NO package managers or external network commands allowed" in prompt

    task2 = make_task(objective="normal task")
    prompt2 = AntigravityLiveBridge()._build_task_prompt(task2, tmp_path, is_new_project=True)
    assert "NO package managers or external network commands allowed" not in prompt2


def test_node_in_allowed_gate_executables():
    from alpha_core.config import settings

    assert "node" in settings.ALLOWED_GATE_EXECUTABLES


def test_declared_vs_undeclared_browser_smoke_prompt(tmp_path):
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    # undeclared
    task = make_task()
    assert task.acceptance_plan.browser_smoke_url is None
    prompt = AntigravityLiveBridge()._build_task_prompt(task, tmp_path, is_new_project=True)
    assert "Browser smoke is NOT independently declared" in prompt
    assert "Do NOT trigger browser-driver/download/install attempts" in prompt

    # declared
    task_declared = make_task()
    task_declared.acceptance_plan.browser_smoke_url = "http://localhost:3000"
    prompt_declared = AntigravityLiveBridge()._build_task_prompt(
        task_declared, tmp_path, is_new_project=True
    )
    assert "Browser smoke is declared" in prompt_declared
    assert "gather browser/E2E" in prompt_declared
    assert "NOT independently declared" not in prompt_declared


def test_qa_audit_declared_vs_undeclared_browser_smoke_prompt(tmp_path):
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    # undeclared
    task = make_task()
    prompt = AntigravityLiveBridge()._build_qa_audit_prompt(task, tmp_path)
    assert "Browser smoke is NOT independently declared" in prompt
    assert "Do NOT attempt browser server" in prompt

    # declared
    task_declared = make_task()
    task_declared.acceptance_plan.browser_smoke_url = "http://localhost:3000"
    prompt_declared = AntigravityLiveBridge()._build_qa_audit_prompt(task_declared, tmp_path)
    assert "start local preview and exercise primary flows" in prompt_declared
    assert "NOT independently declared" not in prompt_declared


def test_agy_result_fails_closed_on_browser_tool_when_dependency_free():
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    events = valid_events()
    events.insert(
        0,
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "call_mcp_tool",
                "tool_info": {
                    "parameters": {"ServerName": "chrome-devtools-mcp", "ToolName": "navigate_page"}
                },
            },
        },
    )

    raw = {"returncode": 0, "events": events, "stderr": ""}
    # dependency-free mode
    result = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        forbid_external_dependencies=True,
    )
    assert result.completed is False
    assert "Forbidden browser tool usage detected" in (result.blocked_reason or "")

    # normal mode
    result_normal = AntigravityLiveBridge._parse_agy_result(
        raw,
        expected_qa_gates=("unit_test",),
        expected_project_id="prj_calculator",
        forbid_external_dependencies=False,
    )
    assert result_normal.completed is True


def test_qa_audit_prompt_allowed_paths_and_hygiene(tmp_path):
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge

    # 1. Docs-only task
    task_docs = make_task()
    task_docs.allowed_paths = ["TODO.md", "docs/CURRENT_REPORT.md"]
    prompt_docs = AntigravityLiveBridge()._build_qa_audit_prompt(task_docs, tmp_path)

    assert "TODO.md, docs/CURRENT_REPORT.md" in prompt_docs
    assert "do NOT modify it" in prompt_docs
    assert "add or repair .gitignore" not in prompt_docs
    assert "edit ONLY the paths listed in 'Allowed paths'" in prompt_docs
    assert "outside allowed paths, do NOT modify it" in prompt_docs

    # 2 & 3. .gitignore explicitly allowed
    task_git = make_task()
    task_git.allowed_paths = [".gitignore", "alpha_core/api/app.py"]
    prompt_git = AntigravityLiveBridge()._build_qa_audit_prompt(task_git, tmp_path)

    assert "add or repair .gitignore" in prompt_git
    assert "edit ONLY the paths listed in 'Allowed paths'" in prompt_git
