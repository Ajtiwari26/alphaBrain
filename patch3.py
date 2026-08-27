with open("testscript/test_live_kernel_safety.py", "r") as f:
    lines = f.readlines()
    
for i, line in enumerate(lines):
    if "from testscript import run_live_kernel_proof" in line:
        lines.pop(i)
        break

for i, line in enumerate(lines):
    if "from unittest.mock import AsyncMock, MagicMock" in line:
        lines.insert(i + 1, "    from testscript import run_live_kernel_proof\n")
        break

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.writelines(lines)
