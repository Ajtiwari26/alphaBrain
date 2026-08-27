with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

text = text.replace(
    'audit_rec = audit_query.scalar_one()',
    'audit_rec = audit_query.scalars().first()'
)

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
