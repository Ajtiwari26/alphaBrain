import re
with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace(
    'manifest_str = \'ALPHA_BRAIN_QA_EVIDENCE:{"contract_version": 1, "project_id": "prj_calculator", "task_id": "task_1", "executed_commands": [{"command": "pytest", "exit_code": 0, "summary": "ok"}], "required_gates": ["unit_test"], "passed_gates": ["unit_test"], "review_calls": 2, "security_review": {"executed": true}, "artifacts": [], "blockers": []}\'',
    'manifest_str = \'ALPHA_BRAIN_QA_EVIDENCE:{"contract_version": 1, "skill": "multi-agent-sdlc", "testscript_root": "testscript", "project_id": "prj_calculator", "task_id": "task_1", "executed_commands": [{"command": "pytest", "exit_code": 0, "summary": "ok"}], "required_gates": ["unit_test"], "passed_gates": ["unit_test"], "review_calls": 2, "security_review": {"executed": true}, "artifacts": [], "blockers": []}\''
)

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
