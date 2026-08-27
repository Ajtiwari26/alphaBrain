# Packet D0-1 — Restore Repository Quality Gates

**Supervisor:** Codex senior review  
**Executor:** AGY  
**Risk:** low  
**Production side effects:** forbidden  
**Commit, merge, push, deploy:** forbidden

## Objective

Fix only current repository-wide Ruff, Ruff-format, and mypy failures. Preserve runtime behavior
and existing tests.

## Allowed files

- `alpha_core/policy/action_broker.py`
- `alpha_core/policy/notification_policy.py`
- `alpha_core/state/task_engine.py`
- `testscript/test_config_and_logging.py`
- `testscript/test_control_plane_p4.py`

No other file may change. Existing dirty files outside this list belong to founder and must remain
untouched.

## Known findings

- Ruff import ordering in action broker and tests.
- Ruff whitespace and constant-assert findings in `test_config_and_logging.py`.
- Ruff unused import/unpacked values in `test_control_plane_p4.py`.
- Ruff formatter drift in notification policy and config/logging test.
- mypy `no-any-return` findings in `TaskEngine.get_worker()` and `TaskEngine.get_task()`.

## Implementation constraints

1. Make narrow semantic fixes. Do not add ignores, `# noqa`, `type: ignore`, casts hiding `Any`,
   or weaker mypy/Ruff configuration.
2. Preserve public function signatures and state-machine behavior.
3. Replace constant assertions with explicit test failure behavior preserving test intent.
4. Do not rewrite tests merely to make incorrect runtime behavior pass.
5. No package install, network command, browser automation, migration, secret access, cleanup,
   generated patch scripts, or roadmap edit.
6. Do not run Git commit, merge, reset, stash, clean, checkout, or push.

## Exact gates

Run from repository root:

```bash
.venv/bin/ruff check alpha_core alpha_protocol alpha_worker alpha_meet testscript
.venv/bin/ruff format --check alpha_core alpha_protocol alpha_worker alpha_meet testscript
.venv/bin/mypy alpha_core alpha_protocol alpha_worker alpha_meet
.venv/bin/pytest -q --disable-warnings
```

## Required output

Return:

- changed-file list;
- concise explanation per file;
- exact command and exit code for every gate;
- unresolved blocker, if any;
- `ALPHA_BRAIN_TASK_DONE` only when all four gates pass;
- otherwise `ALPHA_BRAIN_TASK_BLOCKED: <reason>`.

Stop immediately if any required fix needs a file outside allowed list.

