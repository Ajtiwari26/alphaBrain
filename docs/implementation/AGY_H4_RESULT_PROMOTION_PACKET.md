# PACKET H4 — Founder-approved result promotion

## Role

You are AGY junior executor. Senior architecture below is frozen. Implement it; do not redesign
authority boundaries. Work only in `/Users/ajaytiwari/Desktop/Projects/alphaBrain`.

## Base and branch

- Required base: `c7f3df1993704ae867bd2614f0b860c329640153`.
- Create branch: `alpha/h4-result-promotion`.
- Preserve untracked user file `alpha_meet/frontend/.gitignore`; never stage, edit, delete, or move it.
- Keep all tests/helpers under `testscript/`.
- Stop after local commit. Never push, deploy, migrate, install, reset, stash, clean, or mutate remote
  services.

## Problem

Worker commits verified changes to `alpha/<task_id>` worktree branch, but source repository never
integrates that commit. Downstream tasks frozen to original base would test old code. AlphaBrain must
not claim autonomous multi-task development until result commits can be safely promoted.

## Observable outcome

After exact founder task review succeeds:

1. Control plane creates a distinct pending `task_promotion` approval bound to exact attempt and
   canonical promotion digest.
2. Founder/admin separately approves or rejects promotion using exact digest.
3. Only worker that produced attempt may fetch approved promotion.
4. Mac worker performs idempotent `git merge --ff-only <result_commit>` into currently checked-out
   source branch only when every invariant below passes.
5. Worker reports promotion outcome. Control plane records immutable audit event.
6. Successful or failed outcome is not delivered repeatedly. Crash after local fast-forward but before
   result report recovers idempotently because source HEAD already equals result commit.

## Canonical promotion authority

Create typed protocol DTOs for promotion request/result. Promotion digest must use canonical JSON with
sorted keys and compact separators over only these fields:

- task_id
- project_id
- attempt_id
- worker_id
- repo
- base_commit
- result_commit
- sorted files_changed
- review_sha256

No timestamps, mutable status, logs, paths outside task envelope, or secrets in digest.

Create pending `task_promotion` only when founder approves `task_review`, attempt changed files, and
`result_commit != base_commit`. No-op result needs no promotion. Do not reuse task-execution or review
approval as merge authority.

## API ownership

Add minimal typed endpoints following current auth patterns:

- Founder/admin promotion decision endpoint. Require exact promotion digest and project access.
- Worker-only next-promotion endpoint scoped to `{worker_id}` and verified worker identity.
- Worker-only promotion-result endpoint. URL/body task IDs must match.

Do not expose arbitrary repo/commit values from request bodies. Promotion request must be reconstructed
from persisted TaskRecord + AttemptRecord + approved task-review + approved task-promotion rows.

## Mac promotion invariants

Implement narrow method in `WorktreeManager`; use argument-vector subprocess calls, never shell.

Before mutation:

- Repository path passes existing local validation and configured root binding.
- Source repository working tree and index are clean.
- Current source HEAD equals exact task `base_commit`, OR equals exact `result_commit` for idempotent
  crash recovery.
- `base_commit` and `result_commit` resolve as commits.
- Base is ancestor of result.
- Task branch `refs/heads/alpha/<task_id>` exists and points exactly to result commit.
- `git diff --name-only base..result` equals normalized persisted attempt `files_changed` exactly.
- Every changed file stays inside task `allowed_paths`; `.` remains supported only for legacy tasks.

Mutation:

- Run `git merge --ff-only <result_commit>` from source repository.
- Verify HEAD equals result commit and repository remains clean.
- Never rebase, cherry-pick, force, resolve conflicts, delete branch, or push.

Failure:

- Return sanitized bounded failure without repository mutation.
- Record `task_promotion_failed`; do not auto-retry. Founder must create repair/rebase task later.

## Worker scheduling

Remote Mac worker checks one approved promotion before leasing new coding task. Promotion work is local
Git control work, not AGY/model execution. Add ControlPlaneClient typed methods. Network outage must use
existing failure classification and must not mutate repo without durable approved promotion payload.

## Persistence

Reuse existing ApprovalRecord, AttemptRecord, TaskRecord, AuditEventRecord. No migration/new table.
Pending approval and outcome audit create one durable state machine:

- task_review approved -> task_promotion pending
- task_promotion approved -> worker may fetch
- promotion succeeded/failed -> terminal audit outcome
- promotion rejected -> no worker action

Queries must be deterministic. Reject ambiguous/multiple approvals. PostgreSQL and SQLite compatible.

## Required tests

All new tests under `testscript/`. At minimum prove:

1. Review approval creates exactly one digest-bound pending promotion.
2. Repeated review decision is idempotent; no duplicate promotion approval.
3. Wrong promotion digest rejects without state change.
4. Service/client/other worker cannot approve/fetch/report.
5. Worker fetch reconstructs values from DB, never caller input.
6. Clean exact-base temporary Git repo fast-forwards successfully.
7. Already-at-result recovery reports success without new commit/mutation.
8. Dirty repo fails unchanged.
9. Moved source HEAD fails unchanged.
10. Missing/wrong task branch fails unchanged.
11. Changed-file mismatch and disallowed path fail unchanged.
12. Successful result report is idempotent and not fetched again.
13. Failed result is terminal and not auto-retried.
14. Worker checks promotions before leasing code.
15. Control-plane outage causes no Git mutation.

Use real temporary Git repositories for Git behavior. No mocks may substitute for merge safety proofs.

## Acceptance gates

Run exactly:

```bash
.venv/bin/pytest -q <new focused test files>
.venv/bin/pytest -q testscript/test_state_engine.py testscript/test_control_plane.py testscript/test_security_boundaries.py testscript/test_worktree_security.py
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy alpha_core alpha_protocol alpha_worker alpha_meet
node --check alpha_meet/frontend/js/meet.js
git diff --check c7f3df1993704ae867bd2614f0b860c329640153..HEAD
git status --short
```

If named legacy test path does not exist, report it and run nearest existing worktree/security test;
do not fabricate evidence.

## Reject conditions

Reject own implementation if any occurs:

- Merge happens from review approval without separate promotion approval.
- Control plane performs local Git operation.
- Worker accepts repo/base/result/files from untrusted result body instead of persisted request.
- Non-fast-forward strategy exists.
- Dirty or moved source can mutate.
- Failed promotion automatically retries.
- Multi-task planner is enabled before this packet passes.
- Any test is skipped/xfail to hide missing behavior.
- Any remote mutation occurs.

## Report

Return packet, branch, base, commit SHA, changed files, focused/full gate outputs, real-Git proof cases,
remote mutation confirmation, security findings, remaining risks, and ACCEPT/REJECT decision. Stop.
