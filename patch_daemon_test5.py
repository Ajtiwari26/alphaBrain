with open("testscript/test_daemon_submit.py", "r") as f:
    text = f.read()

text = text.replace(
    '    daemon.health_checker.evaluate_worker_health.return_value = ("ok", {})',
    '    daemon.health_checker.evaluate_worker_health.return_value = ("ok", {})\n    daemon.worktree_mgr = MagicMock()\n    daemon.worktree_mgr.create_worktree.return_value = "/tmp/worktree"'
)

text = text.replace(
    'assert "Failed to persistently submit result for task" in log_output',
    'assert "Failed to persistently submit result for task tsk_123" in log_output'
)

with open("testscript/test_daemon_submit.py", "w") as f:
    f.write(text)
