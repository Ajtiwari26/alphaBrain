with open("testscript/test_live_kernel_safety.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_last_test = False
for line in lines:
    if "async def test_main_live_with_approve_as_called_correctly" in line:
        in_last_test = True
    
    if in_last_test and "captured = capsys.readouterr()" in line:
        new_lines.append('    mock_engine_cls.assert_called_once_with("sqlite+aiosqlite:////fake/path/live_kernel.db", echo=False)\n')
        new_lines.append('    mock_session_factory.assert_called_once_with(mock_engine, expire_on_commit=False)\n')
        
    new_lines.append(line)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.writelines(new_lines)
