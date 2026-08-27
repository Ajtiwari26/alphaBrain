with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

text = text.replace('f"Forbidden browser tool usage detected"', '"Forbidden browser tool usage detected"')

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
