with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace(
    '        raw, expected_qa_gates=("unit_test",), expected_project_id="prj_calculator"\n    )',
    '        raw, expected_qa_gates=("unit_test",), expected_project_id="prj_calculator", forbid_external_dependencies=True\n    )'
)

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
