with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

text = text.replace(
    'status=TaskStatus.RUNNING.value, lease_token="tkn1", worker_id="wrk_1",\n',
    'status=TaskStatus.RUNNING.value, lease_token="tkn1", worker_id="wrk_1", lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),\n'
)
text = text.replace(
    'status=TaskStatus.RUNNING.value, lease_token="tkn2", worker_id="wrk_1",\n',
    'status=TaskStatus.RUNNING.value, lease_token="tkn2", worker_id="wrk_1", lease_expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),\n'
)

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
