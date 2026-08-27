# Packet D1-2R — State Engine Contract Repair

**Supervisor:** Codex senior engineer  
**Executor:** AGY using `gemini-3.1-pro-high`, effort `high`  
**Risk:** medium; durable task-state semantics  
**Production, migration, account, deployment, commit, and push actions:** forbidden

## Proven failure mechanisms

1. `AcceptancePlan` now defaults to both `LINT` and `UNIT_TEST` gates. Four legacy state-engine
   tests submit completed results with only unit-test evidence or no evidence. `submit_result()`
   correctly rejects them. Keep runtime gate enforcement strict; update fixtures to satisfy their
   declared contracts.
2. `decide_task_approval()` contains a function-local import of `TaskStatus`. Python therefore
   treats `TaskStatus` as local throughout the function, causing `UnboundLocalError` on the normal
   task-execution approval branch before that import executes.
3. In-memory SQLite schema creation succeeds. No current evidence supports database corruption.

## Allowed files

- `alpha_core/state/task_engine.py`
- `testscript/test_state_engine.py`
- This packet only for factual execution notes

Do not modify models, migrations, protocol gate defaults, router files, credentials, configuration,
or other tests.

## Required repair

### Runtime

- Remove function-local shadowing of `TaskStatus` in `decide_task_approval()`.
- Use existing module-level protocol imports, or import only names not already module-owned.
- Preserve packet/review digest verification, transitions, audit events, and approval semantics.
- Remove nearby redundant local imports only when behavior cannot change.

### Tests

- Preserve secure default `AcceptancePlan` requiring `LINT` and `UNIT_TEST`.
- Add a small test helper that builds passing evidence for every gate declared by default.
- Use bound task and attempt IDs; do not insert unrelated or fake success shortcuts.
- Update these tests to submit truthful default-gate evidence:
  - `test_result_submission_with_gates`
  - `test_duplicate_result_is_idempotent_and_stale_result_is_rejected`
  - `test_resubmission_cannot_replace_verified_task`
  - `test_dependency_blocks_downstream_then_verified_upstream_unblocks_it`
- Keep approval test proving waiting tasks cannot lease, approved tasks become queued/leaseable,
  and duplicate decisions return `None`.
- Add regression assertion covering normal task-execution approval path so local import shadowing
  cannot return.

## Required gates

Run from AlphaBrain root:

```bash
# Prove complete state-engine lifecycle suite.
.venv/bin/pytest -q testscript/test_state_engine.py

# Prove API/workflow callers did not regress.
.venv/bin/pytest -q testscript/test_api_and_workflow.py testscript/test_control_plane.py

# Prove focused formatting and lint quality.
.venv/bin/ruff check alpha_core/state/task_engine.py testscript/test_state_engine.py
.venv/bin/ruff format --check alpha_core/state/task_engine.py testscript/test_state_engine.py

# Prove static typing for changed runtime file using repository configuration.
.venv/bin/mypy alpha_core/state/task_engine.py
```

Also run `git diff --check` for allowed files and report exact changed paths. If a gate fails, return
`ALPHA_BRAIN_TASK_BLOCKED` with evidence. Never weaken gate policy to make tests pass.

