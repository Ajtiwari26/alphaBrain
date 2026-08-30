with open("alpha_core/api/app.py") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "checkpoints/latest" in line:
        for j in range(i, i + 30):
            print(lines[j], end="")
        break
