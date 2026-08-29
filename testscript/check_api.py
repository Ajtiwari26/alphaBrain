
with open("testscript/tmp_c4/api.log") as f:
    lines = f.readlines()
print(f"Total lines: {len(lines)}")
print("Last 20 lines:")
for line in lines[-20:]:
    print(line.strip())
