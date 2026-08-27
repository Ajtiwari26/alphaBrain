with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

text = text.replace(
    'audit_query = await session.execute(select(AuditEventRecord).where(AuditEventRecord.task_id == "tsk_124"))',
    'audit_query = await session.execute(select(AuditEventRecord).where(AuditEventRecord.task_id == "tsk_124").where(AuditEventRecord.event_type == "result_submitted"))'
)

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
