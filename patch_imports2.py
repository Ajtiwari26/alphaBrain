with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace("import pytest\nfrom unittest.mock import MagicMock\n", "")

# insert after import json
text = text.replace("import json\n", "import json\nimport pytest\nfrom unittest.mock import MagicMock\n")

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
