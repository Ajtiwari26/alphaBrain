with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace(
    '    assert QA_EVIDENCE_TOKEN in prompt\n    assert \'"contract_version": 1\' in prompt',
    '    assert QA_EVIDENCE_TOKEN in prompt\n    assert \'"contract_version": 1\' in prompt\n    # Exact regression test: no double colon or newline between token and JSON\n    assert f"{QA_EVIDENCE_TOKEN}{{\\"contract_version\\": 1" in prompt\n    assert f"{QA_EVIDENCE_TOKEN}:" not in prompt'
)

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
