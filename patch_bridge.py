with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

text = text.replace(
    '    require_qa_audit: bool = False,\n',
    '    require_qa_audit: bool = False,\n    forbid_external_dependencies: bool = False,\n'
)

# update evaluate_agy_execution_outcome
text = text.replace(
    '    # 4b. Command policy check\n    if policy_violations:',
    '    # 4b. Command policy check\n    if forbid_external_dependencies and policy_violations:'
)

# In AntigravityLiveBridge._parse_agy_result
text = text.replace(
    '        require_qa_audit: bool = False,\n    ) -> AntigravityDispatch:',
    '        require_qa_audit: bool = False,\n        forbid_external_dependencies: bool = False,\n    ) -> AntigravityDispatch:'
)

text = text.replace(
    '            expected_project_id=expected_project_id,\n            require_qa_audit=require_qa_audit,\n        )',
    '            expected_project_id=expected_project_id,\n            require_qa_audit=require_qa_audit,\n            forbid_external_dependencies=forbid_external_dependencies,\n        )'
)

import re

# In AntigravityLiveBridge.dispatch, inject forbid_deps logic before conversation ID
dispatch_logic = """
        ready, reason = self.check_readiness()
        if not ready:
            raise RuntimeError(reason)

        forbid_deps = (
            "dependency-free" in (task.objective or "").lower()
            or "no external dependency acquisition" in (task.objective or "").lower()
            or "dependency-free" in (task.detailed_instructions or "").lower()
            or "no external dependency acquisition" in (task.detailed_instructions or "").lower()
        )
"""
text = text.replace(
    '        ready, reason = self.check_readiness()\n        if not ready:\n            raise RuntimeError(reason)\n',
    dispatch_logic
)

text = text.replace(
    '            expected_project_id=task.project_id,\n        )\n        if not dispatch.conversation_id:',
    '            expected_project_id=task.project_id,\n            forbid_external_dependencies=forbid_deps,\n        )\n        if not dispatch.conversation_id:'
)

text = text.replace(
    '                expected_project_id=task.project_id,\n            )\n            dispatch = replace(',
    '                expected_project_id=task.project_id,\n                forbid_external_dependencies=forbid_deps,\n            )\n            dispatch = replace('
)

text = text.replace(
    '                expected_project_id=task.project_id,\n                require_qa_audit=True,\n            )\n            dispatch = replace(',
    '                expected_project_id=task.project_id,\n                require_qa_audit=True,\n                forbid_external_dependencies=forbid_deps,\n            )\n            dispatch = replace('
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
