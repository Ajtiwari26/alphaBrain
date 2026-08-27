with open("alpha_worker/daemon.py", "r") as f:
    text = f.read()

text = text.replace(
    'leased_tuple = await TaskEngine.lease_next_task(session, self.worker_id)',
    'leased_tuple = await TaskEngine.lease_next_task(\n            session, self.worker_id, lease_duration_seconds=settings.WORKER_LEASE_DURATION_SECONDS\n        )'
)

submit_success_logic = """
            success = await TaskEngine.submit_result(session, result, lease_token, self.worker_id)
            if not success:
                logger.error(f"Failed to persistently submit result for task {envelope.task_id} (lease expired or rejected)")
                return False
            logger.info(f"Completed task {envelope.task_id} with status {result.status.value}")
"""

text = text.replace(
    '            await TaskEngine.submit_result(session, result, lease_token, self.worker_id)\n            logger.info(f"Completed task {envelope.task_id} with status {result.status.value}")',
    submit_success_logic
)

with open("alpha_worker/daemon.py", "w") as f:
    f.write(text)
