with open("alpha_core/state/task_engine.py", "r") as f:
    text = f.read()

import re

# find the place where GateEvidenceRecord is instantiated
old_code = 'id=f"{result.attempt_id}_{ev.evidence_id}"[:64],'

new_code = """id=f"ev_{__import__('base64').urlsafe_b64encode(__import__('hashlib').sha256(f'{result.attempt_id}_{ev.evidence_id}'.encode()).digest()).decode().rstrip('=')}","""

text = text.replace(old_code, new_code)

# Add imports if they don't exist (hashlib, base64)
if 'import hashlib' not in text:
    text = "import hashlib\nimport base64\n" + text

with open("alpha_core/state/task_engine.py", "w") as f:
    f.write(text)
