with open("testscript/test_daemon_submit.py", "r") as f:
    text = f.read()

text = text.replace('logger = logging.getLogger("alpha_worker.daemon")', 'logger = logging.getLogger("alpha_worker")')

with open("testscript/test_daemon_submit.py", "w") as f:
    f.write(text)
