import uuid

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from alpha_core.queue.temporal_workflow import (
    TaskLifecycleWorkflow,
    admit_task,
    complete_task,
    lease_task,
)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Sandbox network isolation prevents downloading Temporal dev server")
async def test_task_lifecycle_workflow():
    # Use start_local to test workflow in real Temporal runtime
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(
            env.client,
            task_queue="task-lifecycle-queue",
            workflows=[TaskLifecycleWorkflow],
            activities=[admit_task, lease_task, complete_task],
        ):
            task_id = str(uuid.uuid4())

            # Start workflow
            handle = await env.client.start_workflow(
                TaskLifecycleWorkflow.run,
                {"task_id": task_id, "foo": "bar"},
                id=f"task-lifecycle-{task_id}",
                task_queue="task-lifecycle-queue",
            )

            # Send lease signal
            await handle.signal(TaskLifecycleWorkflow.signal_lease)

            # Send complete signal
            await handle.signal(TaskLifecycleWorkflow.signal_complete, {"result": "ok"})

            # Wait for workflow completion
            result = await handle.result()

            assert result["task_id"] == task_id
            assert result["final_status"] == "completed"
            assert result["result"] == {"result": "ok"}


@pytest.mark.asyncio
@pytest.mark.skip(reason="Sandbox network isolation prevents downloading Temporal dev server")
async def test_task_lifecycle_workflow_timeout():
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(
            env.client,
            task_queue="task-lifecycle-queue",
            workflows=[TaskLifecycleWorkflow],
            activities=[admit_task, lease_task, complete_task],
        ):
            task_id = str(uuid.uuid4())

            handle = await env.client.start_workflow(
                TaskLifecycleWorkflow.run,
                {"task_id": task_id},
                id=f"task-lifecycle-{task_id}",
                task_queue="task-lifecycle-queue",
            )

            # Send cancel signal to force exit and avoid waiting hours in test
            await handle.signal(TaskLifecycleWorkflow.signal_cancel)

            result = await handle.result()
            assert result["final_status"] == "cancelled"

@pytest.mark.asyncio
@pytest.mark.skip(reason="Sandbox network isolation prevents downloading Temporal dev server")
async def test_task_lifecycle_workflow_missing_id():
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(
            env.client,
            task_queue="task-lifecycle-queue",
            workflows=[TaskLifecycleWorkflow],
            activities=[admit_task, lease_task, complete_task],
        ):
            # Start workflow without task_id
            with pytest.raises(Exception) as exc:
                await env.client.execute_workflow(
                    TaskLifecycleWorkflow.run,
                    {}, # Missing task_id
                    id="missing-id-test",
                    task_queue="task-lifecycle-queue",
                )
            assert "task_id is required" in str(exc.value)
