with open("alpha_core/state/task_engine.py", "r") as f:
    text = f.read()

text = text.replace(
    '    AttemptRecord,',
    '    AttemptRecord,\n    GateEvidenceRecord,'
)

evidence_insertion = """
        if result.gate_result and result.gate_result.evidence_items:
            for ev in result.gate_result.evidence_items:
                evidence_rec = GateEvidenceRecord(
                    id=ev.evidence_id,
                    task_id=result.task_id,
                    attempt_id=result.attempt_id,
                    gate_type=ev.gate_type.value,
                    passed=ev.passed,
                    summary=ev.summary,
                    output_log=ev.output_log,
                    metrics_json=ev.metrics,
                    created_at=ev.timestamp,
                )
                session.add(evidence_rec)
"""

text = text.replace(
    '        session.add(attempt)\n\n        TaskEngine._transition(task, target_status)',
    '        session.add(attempt)\n' + evidence_insertion + '\n        TaskEngine._transition(task, target_status)'
)

with open("alpha_core/state/task_engine.py", "w") as f:
    f.write(text)
