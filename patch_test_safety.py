with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

text = text.replace(
    'assert cmds[0].executable == "npm"\n    assert cmds[0].args == ["--prefix", "testscript", "run", "lint"]\n    assert cmds[1].gate_type.value == "unit_test"\n    assert cmds[1].executable == "npm"\n    assert cmds[1].args == ["--prefix", "testscript", "test"]\n    assert "package.json scripts for \'lint\' and \'test\'" in submitted_envelope.objective',
    'assert cmds[0].executable == "node"\n    assert cmds[0].args == ["testscript/lint.mjs"]\n    assert cmds[1].gate_type.value == "unit_test"\n    assert cmds[1].executable == "node"\n    assert cmds[1].args == ["testscript/test.mjs"]\n    assert "no package.json, no node_modules" in submitted_envelope.objective'
)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
