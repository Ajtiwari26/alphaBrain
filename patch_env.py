with open(".env.example", "r") as f:
    text = f.read()

text = text.replace(
    "ANTIGRAVITY_MODEL=gemini-3.7-flash-high",
    "ANTIGRAVITY_MODEL=gemini-3.7-flash-high\nANTIGRAVITY_EFFORT=high"
)

with open(".env.example", "w") as f:
    f.write(text)
