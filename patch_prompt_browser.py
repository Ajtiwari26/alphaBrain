with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

browser_rule_builder = """
        if task.acceptance_plan.browser_smoke_url:
            browser_rule = "Browser smoke is declared. You must gather browser/E2E + keyboard + responsive evidence using browser capabilities."
        else:
            browser_rule = "Browser smoke is NOT independently declared. Do NOT trigger browser-driver/download/install attempts. You may attach existing local evidence but no network acquisition."
"""

text = text.replace(
    '        project_note = (',
    browser_rule_builder + '\n        project_note = ('
)

text = text.replace(
    'If user-facing UI: additionally gather browser/E2E + keyboard + responsive evidence.',
    '{browser_rule}'
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
