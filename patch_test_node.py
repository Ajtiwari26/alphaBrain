with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text += """
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
"""

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
