with open("alpha_core/state/task_engine.py", "r") as f:
    text = f.read()

# Replace the dynamic import with a proper one
text = text.replace(
    'f"ev_{__import__(\'base64\').urlsafe_b64encode(__import__(\'hashlib\').sha256(f\'{result.attempt_id}_{ev.evidence_id}\'.encode()).digest()).decode().rstrip(\'=\')}"',
    'f"ev_{base64.urlsafe_b64encode(hashlib.sha256(f\'{result.attempt_id}_{ev.evidence_id}\'.encode()).digest()).decode().rstrip(\'=\')}"'
)

with open("alpha_core/state/task_engine.py", "w") as f:
    f.write(text)
