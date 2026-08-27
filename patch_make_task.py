with open("testscript/test_antigravity_live_bridge.py", "r") as f:
    text = f.read()

text = text.replace('objective="Build calculator",', 'objective=objective,')

with open("testscript/test_antigravity_live_bridge.py", "w") as f:
    f.write(text)
