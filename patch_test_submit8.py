with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

text = text.replace(
    'lease_expires_at=datetime.now(UTC) + timedelta(hours=1),',
    'lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),'
)

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
