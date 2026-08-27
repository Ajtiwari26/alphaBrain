with open("alpha_core/state/task_engine.py", "r") as f:
    text = f.read()

text = text.replace(
    'return json.loads(val)',
    'res = json.loads(val)\n            return res if isinstance(res, dict) else {}'
)
text = text.replace(
    '            return (\n                existing_attempt.task_id == result.task_id\n                and existing_attempt.status == result.status.value\n                and existing_attempt.result_commit == result.result_commit\n            )',
    '            return bool(\n                existing_attempt.task_id == result.task_id\n                and existing_attempt.status == result.status.value\n                and existing_attempt.result_commit == result.result_commit\n            )'
)

with open("alpha_core/state/task_engine.py", "w") as f:
    f.write(text)
