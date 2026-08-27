with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

assert_code = """
    mock_engine_cls.assert_called_once_with("sqlite+aiosqlite:////fake/path/live_kernel.db", echo=False)
    mock_session_factory.assert_called_once_with(mock_engine, expire_on_commit=False)
"""

text = text.replace("    captured = capsys.readouterr()", assert_code + "    captured = capsys.readouterr()")

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
