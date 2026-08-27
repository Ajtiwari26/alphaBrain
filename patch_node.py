with open("alpha_core/config.py", "r") as f:
    text = f.read()

text = text.replace(
    '        "ALLOWED_GATE_EXECUTABLES",\n        "pytest,ruff,mypy,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go",',
    '        "ALLOWED_GATE_EXECUTABLES",\n        "pytest,ruff,mypy,node,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go",'
)

with open("alpha_core/config.py", "w") as f:
    f.write(text)

with open(".env.example", "r") as f:
    text = f.read()

text = text.replace(
    'ALLOWED_GATE_EXECUTABLES=pytest,ruff,mypy,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go',
    'ALLOWED_GATE_EXECUTABLES=pytest,ruff,mypy,node,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go'
)

with open(".env.example", "w") as f:
    f.write(text)
