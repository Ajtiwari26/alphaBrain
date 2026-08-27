with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text += """
def test_valid_version_1_manifest_is_accepted():
    manifest_str = 'ALPHA_BRAIN_QA_EVIDENCE:{"contract_version": 1, "project_id": "prj_calculator", "task_id": "task_1", "executed_commands": [{"command": "pytest", "exit_code": 0, "summary": "ok"}], "required_gates": ["unit_test"], "passed_gates": ["unit_test"], "review_calls": 2, "security_review": {"executed": true}, "artifacts": [], "blockers": []}'
    response = f"{manifest_str}\\n{COMPLETION_TOKEN}"
    raw = {"returncode": 0, "events": valid_events(response), "stderr": ""}
    result = AntigravityLiveBridge._parse_agy_result(
        raw, expected_qa_gates=("unit_test",), expected_project_id="prj_calculator"
    )
    assert result.completed is True

def test_agy_result_fails_closed_on_unauthorized_commands():
    from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge
    events = valid_events()
    events.insert(0, {
        "event": "step_update",
        "step_update": {
            "step_type": "tool",
            "tool_name": "run_command",
            "tool_info": {
                "parameters": {
                    "CommandLine": "npm install playwright"
                }
            }
        }
    })
    
    raw = {"returncode": 0, "events": events, "stderr": ""}
    result = AntigravityLiveBridge._parse_agy_result(
        raw, expected_qa_gates=("unit_test",), expected_project_id="prj_calculator"
    )
    assert result.completed is False
    assert "Forbidden command execution detected" in (result.blocked_reason or "")
    assert "npm install" in (result.blocked_reason or "")
"""

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
