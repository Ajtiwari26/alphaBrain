with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace(
    'def make_task(\n    project_id: str = "prj_calculator",\n    session_id: str | None = None,\n    repo: str = "/tmp/alpha-calculator-repo",\n) -> TaskEnvelope:\n    return TaskEnvelope(',
    'def make_task(\n    project_id: str = "prj_calculator",\n    session_id: str | None = None,\n    repo: str = "/tmp/alpha-calculator-repo",\n    objective: str = "objective"\n) -> TaskEnvelope:\n    return TaskEnvelope('
)

text = text.replace(
    '        objective="Write a calculator",',
    '        objective=objective,'
)

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
