with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

import re

inject_rule = """
        forbid_deps = (
            "dependency-free" in (task.objective or "").lower()
            or "no external dependency acquisition" in (task.objective or "").lower()
            or "dependency-free" in (task.detailed_instructions or "").lower()
            or "no external dependency acquisition" in (task.detailed_instructions or "").lower()
        )
        dependency_rule = (
            "\\n- NO package managers or external network commands allowed. This is a strict dependency-free execution."
            if forbid_deps else ""
        )
"""
text = text.replace(
    '    def _build_task_prompt(\n        self, task: TaskEnvelope, worktree_path: Path, is_new_project: bool\n    ) -> str:\n        project_note = (',
    '    def _build_task_prompt(\n        self, task: TaskEnvelope, worktree_path: Path, is_new_project: bool\n    ) -> str:' + inject_rule + '\n        project_note = ('
)

text = text.replace(
    '- No roadmap changes or broader refactoring beyond task objective.',
    '- No roadmap changes or broader refactoring beyond task objective.{dependency_rule}'
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
