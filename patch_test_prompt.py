import re
with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

def repl(match):
    return """def test_task_prompt_contains_execution_contract(tmp_path):
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

    # Anti-patterns
    assert "No claiming tests pass without actual captured command output" in prompt
    assert "No silent permission denial" in prompt
    assert "No self-approval, no deployments" in prompt
    assert "No roadmap changes or broader refactoring" in prompt
    assert "No invented fallback models" in prompt
"""

text = re.sub(
    r"def test_task_prompt_requires_official_sdlc_protocol.*?assert \"dangerous permission bypasses\" in prompt\n",
    repl,
    text,
    flags=re.DOTALL
)

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
