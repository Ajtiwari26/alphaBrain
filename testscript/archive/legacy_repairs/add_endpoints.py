content = open("alpha_core/api/app.py").read()

new_endpoints = """
from alpha_protocol.task import AppendCheckpointRequest, ResumeDecisionRequest, ResumeDecisionResponse, TaskCheckpoint
from alpha_core.db.models import TaskCheckpointRecord
from datetime import datetime, timezone
import hashlib

@app.post("/api/tasks/{task_id}/checkpoints")
async def append_task_checkpoint(
    task_id: str,
    payload: AppendCheckpointRequest,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:write")

    if task_id != payload.checkpoint.task_id:
        raise HTTPException(status_code=400, detail="URL task_id does not match payload task_id")

    # 1. Fetch task and check lease
    res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    require_project_access(_principal, task.project_id)

    now = datetime.now(timezone.utc)
    if task.status not in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}:
        raise HTTPException(status_code=409, detail="Task is not active or leased")

    if not task.lease_token or task.lease_token != payload.raw_lease_token:
        raise HTTPException(status_code=403, detail="Invalid lease token")

    if task.lease_expires_at and task.lease_expires_at < now:
        raise HTTPException(status_code=403, detail="Stale lease token")

    if task.worker_id and task.worker_id != payload.checkpoint.worker_id:
        raise HTTPException(status_code=403, detail="Worker mismatch")

    # Verify lease_token_hash matches
    expected_hash = hashlib.sha256(payload.raw_lease_token.encode("utf-8")).hexdigest()
    if payload.checkpoint.lease_token_hash != expected_hash:
        raise HTTPException(status_code=400, detail="lease_token_hash mismatch")

    # 2. Check for duplicate/out-of-order sequence
    res_chk = await session.execute(
        select(TaskCheckpointRecord)
        .where(
            TaskCheckpointRecord.task_id == task_id,
            TaskCheckpointRecord.attempt_number == payload.checkpoint.attempt_number,
        )
        .order_by(TaskCheckpointRecord.sequence.desc())
    )
    checkpoints = res_chk.scalars().all()

    for chk in checkpoints:
        if chk.idempotency_key == payload.checkpoint.idempotency_key:
            if chk.payload_digest == payload.checkpoint.payload_digest:
                # Same idempotency key + same digest returns existing checkpoint
                return payload.checkpoint.model_dump()
            else:
                # Same idempotency key + different digest rejects
                raise HTTPException(status_code=409, detail="Idempotency key conflict with different digest")

    highest_seq = checkpoints[0].sequence if checkpoints else 0
    if payload.checkpoint.sequence <= highest_seq:
        raise HTTPException(status_code=409, detail=f"Sequence {payload.checkpoint.sequence} must be > {highest_seq}")

    if payload.checkpoint.sequence != highest_seq + 1:
        raise HTTPException(status_code=409, detail=f"Sequence {payload.checkpoint.sequence} out of order")

    # 3. Create Checkpoint Record
    new_chk = TaskCheckpointRecord(
        id=payload.checkpoint.checkpoint_id,
        task_id=payload.checkpoint.task_id,
        attempt_id=payload.checkpoint.attempt_id,
        worker_id=payload.checkpoint.worker_id,
        attempt_number=payload.checkpoint.attempt_number,
        sequence=payload.checkpoint.sequence,
        project_id=payload.checkpoint.project_id,
        repo_reference=payload.checkpoint.repo_reference,
        base_commit=payload.checkpoint.base_commit,
        worktree_path=payload.checkpoint.worktree_path,
        worktree_head=payload.checkpoint.worktree_head,
        conversation_id=payload.checkpoint.conversation_id,
        execution_stage=payload.checkpoint.execution_stage,
        lease_token_hash=payload.checkpoint.lease_token_hash,
        side_effect_state=payload.checkpoint.side_effect_state.value,
        scrubbed_payload=payload.checkpoint.scrubbed_payload,
        payload_digest=payload.checkpoint.payload_digest,
        idempotency_key=payload.checkpoint.idempotency_key,
        created_at=payload.checkpoint.created_at,
    )
    session.add(new_chk)

    # Also log to engine as scrubbed payload progress if possible, but schema requires it
    # We will just commit it.
    await session.commit()

    return payload.checkpoint.model_dump()


@app.get("/api/tasks/{task_id}/checkpoints/latest")
async def get_latest_task_checkpoint(
    task_id: str,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:read")

    res = await session.execute(
        select(TaskCheckpointRecord)
        .where(TaskCheckpointRecord.task_id == task_id)
        .order_by(TaskCheckpointRecord.attempt_number.desc(), TaskCheckpointRecord.sequence.desc())
        .limit(1)
    )
    chk = res.scalar_one_or_none()
    if not chk:
        raise HTTPException(status_code=404, detail="No checkpoints found for task")

    return TaskCheckpoint(
        checkpoint_id=chk.id,
        task_id=chk.task_id,
        attempt_id=chk.attempt_id,
        worker_id=chk.worker_id,
        attempt_number=chk.attempt_number,
        sequence=chk.sequence,
        project_id=chk.project_id,
        repo_reference=chk.repo_reference,
        base_commit=chk.base_commit,
        worktree_path=chk.worktree_path,
        worktree_head=chk.worktree_head,
        conversation_id=chk.conversation_id,
        execution_stage=chk.execution_stage,
        lease_token_hash=chk.lease_token_hash,
        side_effect_state=chk.side_effect_state,
        scrubbed_payload=chk.scrubbed_payload,
        payload_digest=chk.payload_digest,
        idempotency_key=chk.idempotency_key,
        created_at=chk.created_at,
    ).model_dump()


@app.post("/api/tasks/{task_id}/resume-decision")
async def get_resume_decision(
    task_id: str,
    payload: ResumeDecisionRequest,
    _principal: AuthPrincipal = Depends(require_api_principal),
    session: AsyncSession = Depends(get_db_session),
):
    require_permission(_principal, "task:write")

    res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    require_project_access(_principal, task.project_id)

    # 1. Fetch latest checkpoint
    res_chk = await session.execute(
        select(TaskCheckpointRecord)
        .where(TaskCheckpointRecord.task_id == task_id)
        .order_by(TaskCheckpointRecord.attempt_number.desc(), TaskCheckpointRecord.sequence.desc())
        .limit(1)
    )
    latest_chk = res_chk.scalar_one_or_none()

    if not latest_chk:
        return ResumeDecisionResponse(safe_to_resume=False, reason="No prior checkpoint found").model_dump()

    if latest_chk.payload_digest != payload.latest_checkpoint_digest:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Checkpoint digest mismatch").model_dump()

    if latest_chk.project_id != payload.project_id:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Project ID mismatch").model_dump()

    if latest_chk.repo_reference != payload.repo_reference:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Repository mismatch").model_dump()

    if latest_chk.base_commit != payload.base_commit:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Base commit mismatch").model_dump()

    if latest_chk.worker_id != payload.worker_id:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Worker mismatch for local worktree").model_dump()

    if latest_chk.attempt_id != payload.attempt_id:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Attempt ID mismatch").model_dump()

    if latest_chk.conversation_id != payload.conversation_id:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Conversation ID mismatch").model_dump()

    if latest_chk.worktree_path != payload.worktree_path:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Worktree path mismatch").model_dump()

    if latest_chk.side_effect_state in {"unknown", "committed"}:
        return ResumeDecisionResponse(safe_to_resume=False, reason="Unsafe side-effect state requires review").model_dump()

    # Re-lease the task with a NEW lease token.
    # We must not reuse the old lease token.
    if task.status not in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}:
        # if it failed or something, we can't resume it unless it's running
        return ResumeDecisionResponse(safe_to_resume=False, reason=f"Task is in {task.status} status").model_dump()

    import secrets
    new_token = f"lse_{secrets.token_urlsafe(32)}"
    task.lease_token = new_token
    # Set a new lease token but preserve the worker
    task.worker_id = payload.worker_id
    now = datetime.now(timezone.utc)
    task.lease_expires_at = now + __import__("datetime").timedelta(seconds=1800)

    await session.commit()

    return ResumeDecisionResponse(safe_to_resume=True, new_lease_token=new_token).model_dump()
"""

with open("alpha_core/api/app.py", "a") as f:
    f.write(new_endpoints)
