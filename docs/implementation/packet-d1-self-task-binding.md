# Packet D1-1 — Immutable Self-Task Approval and Result Binding

**Supervisor:** Codex senior review  
**Executor:** AGY with `gemini-3.1-pro-high`, effort `high`  
**Risk:** low  
**Production side effects:** forbidden  
**Commit, merge, push, deploy:** forbidden

## Objective

Bind every AlphaBrain self-development execution approval and worker result to exact canonical
task packet and immutable base commit. Reject stale, missing, or mismatched bindings before code
execution can be accepted.

## Architecture invariant

```text
canonical TaskEnvelope
  -> SHA-256 packet digest
  -> TaskRecord.packet_sha256
  -> ApprovalRecord.scope_sha256
  -> worker TaskResult.packet_sha256 + base_commit
  -> AttemptRecord.packet_sha256
```

For `require_packet_binding=True`, every arrow is mandatory and equality is exact. A task packet
change requires a new task/approval version. Model text cannot override mismatch.

## Allowed files

- `alpha_protocol/task.py`
- `alpha_protocol/__init__.py`
- `alpha_core/db/models.py`
- `alpha_core/db/migrations/versions/e7a9c2f4d601_self_task_packet_binding.py`
- `alpha_core/state/task_engine.py`
- `alpha_core/self_development.py`
- `alpha_core/api/app.py`
- `alpha_worker/adapters/antigravity.py`
- `alpha_worker/daemon.py`
- `testscript/test_self_development_packet_binding.py`
- Existing directly affected tests under `testscript/` only when required for compatibility.

No other source or configuration file may change.

## Required implementation

### 1. Canonical digest contract

Add one shared protocol helper producing SHA-256 hex digest from canonical task-envelope JSON:

- Pydantic JSON-mode values;
- sorted keys;
- compact separators;
- UTF-8;
- no mutable/non-deterministic post-processing;
- same semantic packet returns same digest across processes.

Add `TaskEnvelope.require_packet_binding: bool = False` for backward compatibility.
Add `TaskResult.packet_sha256: str | None`, validated as 64 lowercase hexadecimal characters when
present.

### 2. Persistence

Add nullable 64-character columns:

- `tasks.packet_sha256`;
- `approvals.scope_sha256`;
- `task_attempts.packet_sha256`.

Create reversible Alembic migration with revision `e7a9c2f4d601`, down revision
`d5e8f1a2b304`. Upgrade adds columns; downgrade removes them. Existing rows remain valid.

### 3. Submission and approval

- `TaskEngine.submit_task()` computes canonical digest and stores it on task.
- Pending execution approval stores same digest in `scope_sha256`.
- Existing task definition cannot be mutated after an approval has been created. Require new task
  ID/version instead; do not reset or silently replace approved scope.
- `create_self_improvement_task()` sets `require_packet_binding=True`.
- Self-development API response exposes `packet_sha256` for founder review.
- Approval API for bound task requires caller-provided `packet_sha256`.
- `decide_task_approval()` approves only when caller digest, task digest, pending approval digest,
  and freshly recomputed canonical digest all match.
- Missing or mismatched digest returns conflict and leaves task waiting for approval.
- Replaying stale approval after packet mutation must fail.

### 4. Lease and result

- Before leasing a bound task, recompute digest from stored envelope and compare with task digest.
  Mismatch must not lease. Record scrubbed audit evidence and block task through legal transition.
- Enabled Antigravity adapter returns task digest in `TaskResult.packet_sha256`.
- Daemon-generated cancelled/error results also carry task digest.
- `TaskEngine.submit_result()` rejects bound result when:
  - digest missing;
  - digest differs from task digest;
  - freshly recomputed task digest differs;
  - result `base_commit` differs from task immutable base commit.
- Accepted attempt persists digest.
- Rejected mismatch must not persist attempt/gate evidence or clear active lease.

### 5. Tests

Add focused tests proving:

1. Canonical digest determinism.
2. Self-task stores digest on task and pending approval.
3. Correct founder digest approves.
4. Missing/wrong founder digest fails without state mutation.
5. Stored packet mutation after approval cannot lease.
6. Missing/wrong result digest fails without attempt/evidence or lease mutation.
7. Wrong result base commit fails.
8. Correct bound result persists attempt digest.
9. Normal legacy task with `require_packet_binding=False` remains compatible.
10. Migration upgrade and downgrade work through existing migration test seam.

## Non-goals

- No founder review/merge endpoint in this packet.
- No immutable snapshot workflow.
- No Render/Supabase deployment.
- No production migration execution.
- No dependency installation or network access.
- No redesign of task state machine, evidence schema, or AGY conversation management.
- No Git cleanup, commit, stash, reset, checkout, or push.

## Exact gates

Run from repository root:

```bash
.venv/bin/pytest -q testscript/test_self_development_packet_binding.py testscript/test_self_development_admission.py testscript/test_state_engine.py testscript/test_submit_gate_evidence.py testscript/test_database_p3.py
.venv/bin/ruff check alpha_core alpha_protocol alpha_worker alpha_meet testscript
.venv/bin/ruff format --check alpha_core alpha_protocol alpha_worker alpha_meet testscript
.venv/bin/mypy alpha_core alpha_protocol alpha_worker alpha_meet
.venv/bin/pytest -q --disable-warnings
```

## Required AGY workflow

1. Read central architecture and this packet.
2. Call code-review graph `build_or_update_graph_tool` and `get_review_context_tool` before edits.
3. Give maximum five-line implementation plan.
4. Implement only allowed scope.
5. Run exact gates.
6. Call both graph tools after edits; repair material findings.
7. Rerun affected gates after any repair.
8. Return changed files, exact commands, exit codes, migration proof, blockers, and QA manifest.

Emit `ALPHA_BRAIN_TASK_DONE` only when every gate passes. Otherwise emit
`ALPHA_BRAIN_TASK_BLOCKED: <exact reason>`.

