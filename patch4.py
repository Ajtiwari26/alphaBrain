with open("testscript/test_live_kernel_safety.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "mock_engine_cls = MagicMock(return_value=mock_engine)" in line:
        new_lines.append(line)
        new_lines.append("    mock_conn = AsyncMock()\n")
        new_lines.append("    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)\n")
        new_lines.append("    mock_conn.__aexit__ = AsyncMock()\n")
        new_lines.append("    mock_engine.begin = MagicMock(return_value=mock_conn)\n")
        continue
    new_lines.append(line)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.writelines(new_lines)
