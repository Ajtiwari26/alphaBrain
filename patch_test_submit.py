with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

from datetime import timedelta
text = text.replace(
    'lease_token="tkn", worker_id="wrk_1",',
    'lease_token="tkn", worker_id="wrk_1", lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),'
)
text = text.replace(
    'lease_token="tkn2", worker_id="wrk_1",',
    'lease_token="tkn2", worker_id="wrk_1", lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),'
)

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
