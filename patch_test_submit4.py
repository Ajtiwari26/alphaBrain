with open("testscript/test_submit_gate_evidence.py", "r") as f:
    text = f.read()

import re

# We will just print the exception to stdout directly
text = text.replace(
    'async def test_duplicate_evidence_id_across_attempts(test_db_session):',
    'async def test_duplicate_evidence_id_across_attempts(test_db_session):\n    try:'
)

lines = text.split("\n")
new_lines = []
in_func = False
for line in lines:
    if line.startswith('async def test_duplicate_evidence_id_across_attempts'):
        in_func = True
        new_lines.append(line)
        new_lines.append('    try:')
    elif in_func:
        new_lines.append('    ' + line)
    else:
        new_lines.append(line)

new_lines.append("""
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
""")

with open("testscript/test_submit_gate_evidence.py", "w") as f:
    f.write("\n".join(new_lines))
