# Packet D1-2 — Central Evidence Validation and Founder Review Binding

**Supervisor:** Codex senior review  
**Executor:** AGY with `gemini-3.1-pro-high`, effort `high`  
**Risk:** low  
**Production side effects:** forbidden  
**Commit, merge, push, deploy, dependency install, or database mutation:** forbidden

## Objective

Close remaining D1 trust gaps before AlphaBrain runs its first self-development task. Worker claims
must not be enough to complete work. Control plane must independently validate exact gate evidence,
changed-file scope, and result identity, then bind founder review to persisted result.

## Existing invariant

D1-1 already binds execution approval and worker result to canonical task packet and immutable base
commit. Preserve all D1-1 behavior and legacy `require_packet_binding=False` compatibility.

## Allowed files

- `alpha_protocol/task.py`
- `alpha_protocol/__init__.py`
- `alpha_protocol/enums.py` (only the `VERIFIED -> BLOCKED` review-rejection transition)
- `alpha_core/state/task_engine.py`
- `alpha_core/api/app.py`
- `alpha_worker/adapters/base.py`
- `testscript/test_self_development_evidence_review.py`
- Existing directly affected tests only when compatibility requires narrow assertion updates
- This packet document only

No other file may change. Existing dirty files belong to founder and must remain untouched.

## Required design

### 1. Exact command evidence

- `BaseAgentAdapter.run_acceptance_gates()` must store canonical declared argv in every executed
  command evidence item as `metrics["command_argv"] = [executable, *args]` and numeric
  `metrics["exit_code"]`.
- Control plane accepts a declared `GateCommand` only when one passing evidence item has same
  `gate_type`, exact `command_argv`, and `exit_code == 0`.
- Evidence summary text is never authority.

### 2. Central fail-closed evidence validation

Before any result/attempt/evidence/task mutation, `TaskEngine.submit_result()` must reject:

- missing or empty evidence for a successful result;
- `GateResult.task_id != TaskResult.task_id`;
- `GateResult.attempt_id != TaskResult.attempt_id`;
- duplicate `evidence_id` values;
- missing passing evidence for any `AcceptancePlan.required_gates` entry;
- any failed evidence for a required gate;
- missing or mismatched declared-command evidence;
- absolute, parent-traversal, or outside-`allowed_paths` entries in `files_changed`;
- changed files with missing `result_commit`;
- bound result packet/base mismatch already enforced by D1-1.

Rejection returns `False`, retains active lease/task status, and persists no attempt, gate evidence,
or approval.

### 3. Founder review binding for self-development

- A valid successful result for `require_packet_binding=True` enters `VERIFIED`, never
  `COMPLETED` directly.
- Persist attempt and evidence, then create one pending `ApprovalRecord` with
  `approval_type="task_review"` and `scope_sha256` equal to canonical review digest.
- Canonical review digest covers persisted authority fields: task ID, attempt ID, packet digest,
  immutable base commit, result commit, sorted changed files, agent, model, worker identity, and
  canonical gate-result JSON. Exclude volatile timestamps and prose-only fields.
- Export deterministic digest helper from `alpha_protocol`.
- Duplicate identical result submission remains idempotent and creates no duplicate review.
- Review approval must be founder-only through existing API authorization.
- For pending `task_review`, approval request must include exact `review_sha256`. Recompute digest
  from persisted task + attempt data; caller digest, approval scope, and recomputed digest must all
  match.
- Approved review transitions `VERIFIED -> COMPLETED`; rejected review leaves generated code
  unaccepted and transitions to `BLOCKED` with auditable reason. Add only required legal transition.
- Execution approval behavior remains: exact `packet_sha256`, then `WAITING_APPROVAL -> QUEUED`.
- Task detail API exposes pending review digest and approval type without exposing secrets.

### 4. Audit truth

- Successful verified result records existing result audit plus pending-review event.
- Founder review records approved/rejected event containing attempt ID and review digest.
- Never claim generated code accepted before founder review approval.

## Required tests

Add focused tests proving:

1. exact declared argv + exit code passes;
2. summary-only or wrong argv fails without mutation;
3. missing required gate, failed required gate, zero evidence, mismatched task/attempt IDs, and
   duplicate evidence IDs fail closed;
4. absolute, traversal, and outside-scope changed paths fail closed;
5. changed files without result commit fail closed;
6. valid bound result becomes `VERIFIED` and creates exactly one digest-bound pending review;
7. duplicate result creates no duplicate attempt/evidence/review;
8. wrong/missing founder review digest fails without state mutation;
9. correct founder review digest completes task;
10. rejected founder review blocks task and is audited;
11. execution approval remains packet-bound and legacy task flow remains compatible.

## Exact gates

```bash
.venv/bin/pytest -q testscript/test_self_development_evidence_review.py testscript/test_self_development_packet_binding.py testscript/test_submit_gate_evidence.py testscript/test_control_plane_p4.py testscript/test_state_engine.py
.venv/bin/ruff check alpha_core alpha_protocol alpha_worker alpha_meet testscript
.venv/bin/ruff format --check alpha_core alpha_protocol alpha_worker alpha_meet testscript
.venv/bin/mypy alpha_core alpha_protocol alpha_worker alpha_meet
.venv/bin/pytest -q --disable-warnings
```

## Review protocol

Before edits: update code-review graph and inspect impacted callers. After edits: update graph,
request review context for changed files, fix material findings, then run exact gates. Never use
`ruff --fix` or `ruff format` across repository; edit/format only allowed files.

## Stop condition

Stop only when exact gates pass and final response lists changed files, command outputs, remaining
risks, and `ALPHA_BRAIN_TASK_DONE`. Any unresolved gate means `ALPHA_BRAIN_TASK_BLOCKED`.
