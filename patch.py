import sys

with open("testscript/test_live_kernel_safety.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_test = False
for line in lines:
    if "async def test_main_live_with_approve_as_called_correctly" in line:
        in_test = True
        new_lines.append(line)
        continue
        
    if in_test and "from unittest.mock import AsyncMock" in line:
        new_lines.append(line)
        new_lines.append("    mock_engine = AsyncMock()\n")
        new_lines.append("    mock_engine_cls = MagicMock(return_value=mock_engine)\n")
        new_lines.append("    monkeypatch.setattr(run_live_kernel_proof, 'create_async_engine', mock_engine_cls)\n")
        new_lines.append("    mock_session = AsyncMock()\n")
        new_lines.append("    mock_session.__aenter__ = AsyncMock(return_value=mock_session)\n")
        new_lines.append("    mock_session.__aexit__ = AsyncMock()\n")
        new_lines.append("    mock_session_factory = MagicMock(return_value=mock_session)\n")
        new_lines.append("    monkeypatch.setattr(run_live_kernel_proof, 'async_sessionmaker', mock_session_factory)\n")
        continue

    new_lines.append(line)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.writelines(new_lines)
