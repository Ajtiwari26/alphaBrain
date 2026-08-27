with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

import base64
import hashlib

def gen_id(att, evi):
    d = base64.urlsafe_b64encode(hashlib.sha256(f"{att}_{evi}".encode()).digest()).decode().rstrip('=')
    return f"ev_{d}"

id1 = gen_id("att_1", "evi_1")
id2 = gen_id("att_2", "evi_1")

text = text.replace('assert "att_1_evi_1" in ids', f'assert "{id1}" in ids')
text = text.replace('assert "att_2_evi_1" in ids', f'assert "{id2}" in ids')

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write(text)
