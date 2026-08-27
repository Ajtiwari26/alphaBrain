with open(".env.example", "r") as f:
    text = f.read()

text = text.replace(
    'ANTIGRAVITY_EFFORT=high',
    'ANTIGRAVITY_EFFORT=high\nANTIGRAVITY_UNATTENDED_COMMANDS=false'
)

with open(".env.example", "w") as f:
    f.write(text)
