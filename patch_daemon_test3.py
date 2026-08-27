with open("testscript/test_daemon_submit.py", "r") as f:
    text = f.read()

text = text.replace('agent="agy"', 'agent="antigravity"')

with open("testscript/test_daemon_submit.py", "w") as f:
    f.write(text)
