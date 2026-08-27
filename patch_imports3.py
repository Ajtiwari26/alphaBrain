with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("from unittest.mock import MagicMock"): continue
    if line.startswith("import pytest"): continue
    if line.startswith("import json"):
        new_lines.append('import json\nimport pytest\nfrom unittest.mock import MagicMock\n')
        continue
    new_lines.append(line)

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.writelines(new_lines)
