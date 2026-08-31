# PACKET H5 — Autonomous Self-Development Proof Runner

## Objective

Build a resumable operator proof that makes AlphaBrain execute one real low-risk improvement to its own repository through the same authority chain used for client work:

`self-development intake -> execution approval -> Mac worker/AGY -> gates -> review approval -> promotion approval -> ff-only source promotion`

This packet builds and tests the runner. It must not auto-approve or execute the real proof during implementation.

## Exact base and branch

- Repository: `/Users/ajaytiwari/Desktop/Projects/alphaBrain`
- Base: `37cb6602b469b15031ec7c403d1fc29ee6c675d8`
- Create branch: `alpha/h5-self-development-proof`
- Preserve `alpha_meet/frontend/.gitignore` untouched and untracked.

## Context budget

Read only:

1. `docs/implementation/ALPHABRAIN_COMPACT_CONTEXT.md`
2. This packet
3. Code Review Graph queries for self-development endpoint, approval engine, worker cycle, result review, and H4 promotion
4. Exact base..HEAD diff and directly related tests

Do not load historical chat transcripts.

## Real proof task

Runner must prepare this exact bounded task:

- Objective: update `TODO.md` with a concise truthful H4 result-promotion completion/evidence note.
- Allowed path: `TODO.md` only.
- Base commit: exact source HEAD captured at prepare time.
- Risk: low.
- Agent: Antigravity/AGY only. Codex and Claude execution disabled.
- No source mutation before final promotion approval.
- No deployment, migration, push, external call, package install, or production action.

## Runner location and interface

Create:

- `testscript/h5_self_development_proof.py`
- `testscript/test_h5_self_development_proof.py`

Runner must support resumable subcommands:

1. `prepare`
2. `status`
3. `approve-execution --digest <sha256>`
4. `run-worker`
5. `approve-review --digest <sha256>`
6. `approve-promotion --digest <sha256>`
7. `verify`
8. `cleanup`

Each mutating approval subcommand must require both:

- exact current digest, and
- explicit operator confirmation string read from CLI argument.

Never auto-approve from stored state.

## Isolation and persistence

- Start local control plane on `127.0.0.1` with random free port.
- Use temporary proof database and worker state under `testscript/evidence/h5-self-proof/<run_id>/`.
- Use actual AlphaBrain API contracts and outbound `ControlPlaneClient`; no direct DB writes.
- Read-only DB queries are allowed only for final independent evidence if API lacks equivalent endpoint; record this exception explicitly.
- Use current source repository as promotion target, but AGY execution occurs only in `alpha/<task_id>` worktree.
- Persist non-secret run state as JSON: run ID, PIDs, task/project IDs, digests, base/result commits, changed files, statuses, timestamps.
- Never persist tokens, signing secrets, AGY account tokens, or spool key. Load secrets from environment/Keychain.
- Cleanup may stop only proof-owned PIDs and remove only proof-owned temporary state. It must never stop production launchd worker.

## Authority gates

### Execution

`prepare` submits self-development task and prints exact execution approval string. It then stops.

### Review

After worker returns verified result, `status` prints exact review digest and review approval string. It then stops.

### Promotion

After review approval, `status` prints exact promotion digest and promotion approval string. It then stops.

### Completion

Only after promotion approval may `run-worker` apply H4 fast-forward promotion.

Deployment remains forbidden and separate.

## AGY execution requirements

- Use existing AGY adapter and current authenticated account routing.
- New conversation/project context for this task; no unrelated Antigravity chat reuse.
- Prompt includes exact objective, allowed path, base commit, gate commands, and stop conditions.
- Reject any changed file other than `TODO.md`.
- Capture actual result commit and AGY conversation ID.
- No claims from AGY text; only commit/diff/gate evidence counts.

## Gates for real self-task

- `git diff --check <base>..<result>`
- exact changed file set equals `TODO.md`
- `.venv/bin/pytest -q testscript/test_promotion_packet.py`
- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/mypy alpha_core alpha_protocol alpha_worker alpha_meet`

## Required hermetic tests

Tests must not call real AGY or mutate current source. Use temporary Git repositories and fake HTTP/worker boundaries to prove:

1. `prepare` captures exact clean tracked base and creates one task.
2. Unrelated untracked file survives prepare.
3. Every approval rejects missing/wrong digest.
4. Every approval rejects missing/wrong confirmation string.
5. Runner cannot skip execution -> review -> promotion order.
6. Worker run before execution approval performs no AGY call.
7. Review approval cannot authorize promotion.
8. Promotion cannot run before exact founder approval.
9. Resume after process restart reads state and continues correct phase.
10. Duplicate subcommand is idempotent and creates no duplicate task/approval/promotion.
11. Result changing extra file is rejected and source HEAD stays base.
12. Failed gates block review.
13. Successful final promotion advances HEAD exactly to result.
14. Cleanup touches only proof-owned processes/state.
15. State/evidence files contain no configured secret values.

## Allowed implementation scope

- `testscript/h5_self_development_proof.py`
- `testscript/test_h5_self_development_proof.py`
- `docs/implementation/AGY_H5_SELF_DEVELOPMENT_PROOF_PACKET.md`
- `docs/implementation/ALPHABRAIN_COMPACT_CONTEXT.md`
- minimal production files only if runner exposes a proven missing API contract; disclose and justify before edit.

## Reject conditions

- Auto-approval or hard-coded founder decision.
- Direct database write.
- Source mutation before promotion approval.
- Real AGY/network execution inside unit tests.
- Broad process killing.
- Secret persistence/logging.
- Reuse of unrelated AGY chat.
- Changes outside allowed scope without senior approval.
- Push, deploy, migration, install, reset, stash, clean, or remote mutation.

## Verification before local commit

Run:

```bash
.venv/bin/pytest -q testscript/test_h5_self_development_proof.py
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy alpha_core alpha_protocol alpha_worker alpha_meet
node --check alpha_meet/frontend/js/meet.js
git diff --check 37cb6602b469b15031ec7c403d1fc29ee6c675d8..HEAD
```

Stop after one local commit. Report exact outputs and remaining requirements for starting real `prepare`.
