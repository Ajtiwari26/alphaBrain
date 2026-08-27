import re
with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace("    COMPLETION_TOKEN,\n", "    COMPLETION_TOKEN,\n    BLOCKED_TOKEN,\n")

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
