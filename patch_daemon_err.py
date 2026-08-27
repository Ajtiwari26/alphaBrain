with open("alpha_worker/daemon.py", "r") as f:
    text = f.read()

text = text.replace(
    '            await TaskEngine.submit_result(session, failed_result, lease_token, self.worker_id)\n        finally:',
    '            fail_success = await TaskEngine.submit_result(session, failed_result, lease_token, self.worker_id)\n            if not fail_success:\n                logger.error(f"Failed to persistently submit error result for task {envelope.task_id} (lease expired or rejected)")\n                return False\n        finally:'
)

with open("alpha_worker/daemon.py", "w") as f:
    f.write(text)
