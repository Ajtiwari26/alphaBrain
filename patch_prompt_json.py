import re
with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

text = text.replace(
    '{"contract_version": 1, "project_id": "{task.project_id}",',
    '{"contract_version": 1, "skill": "{SDLC_SKILL_NAME}", "testscript_root": "testscript", "project_id": "{task.project_id}",'
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
