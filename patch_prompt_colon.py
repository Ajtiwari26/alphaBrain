with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

text = text.replace(
    'Emit a single-line JSON manifest before termination prefixed with {QA_EVIDENCE_TOKEN}:\\n{{',
    'Emit a single-line JSON manifest before termination prefixed with {QA_EVIDENCE_TOKEN}\\n{{'
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
