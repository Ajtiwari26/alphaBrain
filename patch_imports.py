with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace("from unittest.mock import MagicMock\n\nimport pytest\n", "")

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write("import pytest\nfrom unittest.mock import MagicMock\n" + text)
