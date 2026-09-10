import pytest

from alpha_core.queue.temporal_workflow import (
    TaskLifecycleWorkflow,
    admit_task,
    complete_task,
    lease_task,
)


@pytest.mark.asyncio
async def test_activities():
    payload = {"task_id": "test-123"}

    # Test admit
    res1 = await admit_task(payload)
    assert res1["status"] == "admitted"
    assert res1["task_id"] == "test-123"

    # Test lease
    res2 = await lease_task("test-123")
    assert res2["status"] == "leased"
    assert res2["task_id"] == "test-123"

    # Test complete
    res3 = await complete_task("test-123", {"result": "ok"})
    assert res3["status"] == "completed"
    assert res3["task_id"] == "test-123"
    assert res3["result"] == {"result": "ok"}

def test_workflow_signals():
    # Since testing Temporal workflows without the test server is hard,
    # we just test the basic initialization and signal methods directly.
    wf = TaskLifecycleWorkflow()
    assert wf._status == "pending"
    assert not wf._leased
    assert not wf._completed

    wf.signal_lease()
    assert wf._leased

    wf.signal_complete({"result": "ok"})
    assert wf._completed
    assert wf._result == {"result": "ok"}
