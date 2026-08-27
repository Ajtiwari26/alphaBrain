with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

asserts = """
    mock_task_engine.decide_task_approval.assert_called_once_with(
        unittest.mock.ANY, "t1", approved=True, decided_by="ajaytiwari@example.com"
    )
    
    # Assert envelope commands
    submit_call = mock_task_engine.submit_task.call_args
    assert submit_call is not None
    submitted_envelope = submit_call[0][1]
    cmds = submitted_envelope.acceptance_plan.commands
    assert len(cmds) == 2
    assert cmds[0].gate_type.value == "lint"
    assert cmds[0].executable == "npm"
    assert cmds[0].args == ["--prefix", "testscript", "run", "lint"]
    assert cmds[1].gate_type.value == "unit_test"
    assert cmds[1].executable == "npm"
    assert cmds[1].args == ["--prefix", "testscript", "test"]
    assert "package.json scripts for 'lint' and 'test'" in submitted_envelope.objective
"""

text = text.replace(
    '    mock_task_engine.decide_task_approval.assert_called_once_with(\n        unittest.mock.ANY, "t1", approved=True, decided_by="ajaytiwari@example.com"\n    )',
    asserts
)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
