with open("testscript/test_daemon_submit.py", "r") as f:
    text = f.read()

text = text.replace(
    'envelope = TaskEnvelope(task_id="tsk_123", project_id="prj_1", repo="repo", objective="obj", base_commit="abcd")',
    'from alpha_core.schemas import GateType, GateCommand\nenvelope = TaskEnvelope(task_id="tsk_123", project_id="prj_1", repo="repo", objective="obj", base_commit="abcd", allowed_paths=["."], acceptance_plan=MagicMock())'
)

with open("testscript/test_daemon_submit.py", "w") as f:
    f.write(text)
