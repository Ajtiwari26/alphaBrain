with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

old_args = """        if is_new_project:
            args.insert(1, "--new-project")"""

new_args = """        if settings.ANTIGRAVITY_UNATTENDED_COMMANDS:
            args.append("--dangerously-skip-permissions")
        if is_new_project:
            args.insert(1, "--new-project")"""

text = text.replace(old_args, new_args)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
