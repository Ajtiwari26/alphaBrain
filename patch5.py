with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

text = text.replace("mock_session = AsyncMock()", "mock_session = MagicMock()")

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
