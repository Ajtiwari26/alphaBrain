with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

args_section = """            "--model",
            settings.ANTIGRAVITY_MODEL,"""

new_args_section = """            "--model",
            settings.ANTIGRAVITY_MODEL,
            "--effort",
            settings.ANTIGRAVITY_EFFORT,"""

text = text.replace(args_section, new_args_section)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
