with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

text = text.replace('    try:\n        try:\n', '    try:\n')

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
