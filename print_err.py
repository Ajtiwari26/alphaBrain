from testscript.test_antigravity_live_bridge import *
manifest_str = 'ALPHA_BRAIN_QA_EVIDENCE:{"contract_version": 1, "project_id": "prj_calculator", "task_id": "task_1", "executed_commands": [{"command": "pytest", "exit_code": 0, "summary": "ok"}], "required_gates": ["unit_test"], "passed_gates": ["unit_test"], "review_calls": 2, "security_review": {"executed": true}, "artifacts": [], "blockers": []}'
response = f"{manifest_str}\n{COMPLETION_TOKEN}"
raw = {"returncode": 0, "events": valid_events(response), "stderr": ""}
result = AntigravityLiveBridge._parse_agy_result(
    raw, expected_qa_gates=("unit_test",), expected_project_id="prj_calculator"
)
print("ERROR IS:", result.blocked_reason)
