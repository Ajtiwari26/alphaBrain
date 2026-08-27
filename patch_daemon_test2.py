with open("testscript/test_daemon_submit.py", "r") as f:
    text = f.read()

text = text.replace(
    'RiskClass.STANDARD',
    'RiskClass.LOW'
)
text = text.replace(
    'from alpha_protocol.task import TaskEnvelope, TaskStatus, TaskResult, AcceptancePlan, RiskClass',
    'from alpha_protocol.task import TaskEnvelope, TaskStatus, TaskResult, AcceptancePlan\nfrom alpha_protocol.enums import RiskClass'
)

with open("testscript/test_daemon_submit.py", "w") as f:
    f.write(text)
