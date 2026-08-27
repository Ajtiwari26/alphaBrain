with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

browser_rule_builder = """
        if task.acceptance_plan.browser_smoke_url:
            browser_rule = "For user-facing work, start local preview and exercise primary flows with\\nreal browser clicks, keyboard input, validation errors, responsive layouts, and visual inspection."
        else:
            browser_rule = "Browser smoke is NOT independently declared. Do NOT attempt browser server, browser tool, driver/install/download, curl/wget, or network acquisition. Audit only allowed local source/tests and exact declared gates."
"""

text = text.replace(
    '        required_gates = ", ".join(gate.value for gate in task.acceptance_plan.required_gates)',
    browser_rule_builder + '\n        required_gates = ", ".join(gate.value for gate in task.acceptance_plan.required_gates)'
)

text = text.replace(
    'For user-facing work, start local preview and exercise primary flows with\nreal browser clicks, keyboard input, validation errors, responsive layouts, and visual inspection.',
    '{browser_rule}'
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
