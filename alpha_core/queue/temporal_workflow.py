import logging
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@activity.defn
async def admit_task(payload: dict) -> dict:
    """Admit a new task into the system."""
    logger.info(f"Admitting task: {payload.get('task_id')}")
    return {"status": "admitted", "task_id": payload.get("task_id")}

@activity.defn
async def lease_task(task_id: str) -> dict:
    """Lease a task to a worker."""
    logger.info(f"Leasing task: {task_id}")
    return {"status": "leased", "task_id": task_id}

@activity.defn
async def complete_task(task_id: str, result: dict) -> dict:
    """Complete a task."""
    logger.info(f"Completing task: {task_id}")
    return {"status": "completed", "task_id": task_id, "result": result}


@workflow.defn
class TaskLifecycleWorkflow:
    def __init__(self) -> None:
        self._status = "pending"
        self._leased = False
        self._completed = False
        self._result: dict | None = None

    @workflow.run
    async def run(self, payload: dict) -> dict:
        task_id = payload.get("task_id", "unknown")

        # 1. Admit
        await workflow.execute_activity(
            admit_task,
            payload,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._status = "admitted"

        # Wait for lease signal
        await workflow.wait_condition(lambda: self._leased)

        # 2. Lease
        await workflow.execute_activity(
            lease_task,
            task_id,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._status = "executing"

        # Wait for complete signal
        await workflow.wait_condition(lambda: self._completed)

        # 3. Complete
        await workflow.execute_activity(
            complete_task,
            args=[task_id, self._result or {}],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._status = "completed"

        return {"task_id": task_id, "final_status": self._status}

    @workflow.signal
    def signal_lease(self) -> None:
        self._leased = True

    @workflow.signal
    def signal_complete(self, result: dict) -> None:
        self._result = result
        self._completed = True
