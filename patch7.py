with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

bad_code = """    mock_engine_cls.assert_called_once_with("sqlite+aiosqlite:////fake/path/live_kernel.db", echo=False)
    mock_session_factory.assert_called_once_with(mock_engine, expire_on_commit=False)
"""

# Replace all occurrences of bad_code back to nothing
text = text.replace(bad_code, "")

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
