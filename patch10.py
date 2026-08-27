with open("testscript/test_live_kernel_safety.py", "r") as f:
    text = f.read()

text = text.replace(
    'monkeypatch.setattr(run_live_kernel_proof.subprocess, "run", MagicMock())',
    'monkeypatch.setattr(run_live_kernel_proof, "setup_git_repository", MagicMock())'
)

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.write(text)
