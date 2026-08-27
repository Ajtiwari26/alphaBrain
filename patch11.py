with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

text = text.replace("import subprocess\n", "")
text = text.replace("from testscript.run_live_kernel_proof import setup_git_repository\n", "")
text = text.replace(
    'match="Git setup failed',
    'match=r"Git setup failed'
)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
