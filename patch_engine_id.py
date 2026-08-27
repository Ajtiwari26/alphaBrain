with open("alpha_core/state/task_engine.py", "r") as f:
    text = f.read()

text = text.replace(
    '                    id=ev.evidence_id,',
    '                    id=f"{result.attempt_id}_{ev.evidence_id}"[:64],'
)

with open("alpha_core/state/task_engine.py", "w") as f:
    f.write(text)
