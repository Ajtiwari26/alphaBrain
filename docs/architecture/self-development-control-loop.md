# AlphaBrain Self-Development Control Loop

**Contract version:** 1  
**Status:** implementation authority for supervised self-development milestone

## Objective

Prove AlphaBrain can complete one low-risk AlphaBrain TODO item through its normal task, worker,
AGY, evidence, review, and founder-decision path. Generated code is never trusted because an
agent said it is done.

## Boundary

This milestone includes:

- clean immutable source admission;
- frozen task packet and separate execution approval;
- isolated worktree creation;
- one AGY project conversation bound to exact project and repository;
- structured attempt result and typed evidence;
- independent supervisor gate execution and diff review;
- accept, reject, or refinement decision against exact revision.

This milestone excludes:

- production deployment;
- automatic merging into AlphaBrain source;
- database/DNS/payment/call side effects;
- broad roadmap planning by AGY;
- multiple coding providers;
- autonomous cleanup, stash, commit, or mutation of dirty founder work.

## Ownership

| Owner | Authority | Forbidden |
|---|---|---|
| Founder | Approve scope, execution, refinement, merge, deployment | Implicit approval from chat silence |
| Senior supervisor | Design packet, allowed paths, exact gates, review evidence | Coding-agent self-attestation as proof |
| AlphaBrain | Persist state, enforce policy, lease, recover, record evidence | Accepting its own generated code |
| Mac worker | Create worktree, run adapter, execute gates, return artifacts | Direct production DB or GUI automation |
| AGY | Implement bounded task, run declared gates, report structured output | Roadmap changes, deployment, merge, path escape |

## Durable lifecycle

```text
PROPOSED
  -> ADMISSION_CHECKED
  -> WAITING_APPROVAL
  -> QUEUED
  -> LEASED
  -> EXECUTING
  -> VERIFYING
  -> WAITING_REVIEW
  -> ACCEPTED
       |-> REFINEMENT_QUEUED
       |-> REJECTED

Any active state may enter BLOCKED, FAILED, CANCELLED, or SUPERSEDED through a legal transition.
```

## Immutable self-task packet

Supervisor freezes following fields before queueing:

1. Contract version and SHA-256 contract digest.
2. Project ID, task ID, risk class, and idempotency key.
3. Source repository canonical path and immutable base commit.
4. Objective, explicit non-goals, and maximum changed-file scope.
5. Allowed paths and allowed tools.
6. Exact executable gate commands and required evidence types.
7. Timeout, cancellation, retry, and escalation policy.
8. Expected artifacts and founder decision requirement.

Mutation after approval creates a new packet version. Old approval cannot authorize changed
scope, paths, commands, or base revision.

## AGY context strategy

Central documents hold stable architecture:

- `docs/architecture/autonomous-project-kernel.md`
- `docs/architecture/agy-junior-execution-contract.md`
- `docs/architecture/self-development-control-loop.md`

Every AGY prompt contains only:

- contract version and digest;
- immutable task packet;
- relevant phase rules;
- exact acceptance commands;
- required terminal manifest schema.

Prompt must not paste full roadmap. AGY receives one task, not permission to choose next task.
Conversation may retain project context, but packet remains source of truth when conversation and
packet disagree.

## Model routing

- Default implementation and review model: `gemini-3.1-pro-high` with `high` effort.
- Use default for runtime logic, state machines, security, migrations, self-development, and
  architecture-sensitive work.
- `gemini-3.7-flash-high` is an explicit supervisor-selected exception for mechanical formatting,
  documentation, repetitive test updates, or other low-judgment labor.
- Model selection is persisted with every attempt. Silent fallback is forbidden.
- Passing gates and independent review remain mandatory regardless of model.

## Verification architecture

```text
AGY implementation output
  -> worker checks exit status and path boundary
  -> worker captures diff and declared command output
  -> evidence broker validates typed evidence and hashes
  -> senior supervisor reruns selected gates independently
  -> senior reviews diff against objective and non-goals
  -> founder receives exact revision, evidence, preview, and decision options
```

Success requires all conditions:

- AGY process exit code is zero;
- changed files stay inside allowed paths;
- every required gate has matching passing evidence;
- no required evidence is empty;
- independent gate rerun passes;
- no unresolved high-severity review finding exists;
- founder accepts exact result revision.

`ALPHA_BRAIN_TASK_DONE`, model prose, quiet process, generated preview, or passing unit tests alone
cannot establish acceptance.

## Bootstrap phases

### D0 — Repository truth

Goal: make AlphaBrain source eligible for immutable admission.

- Fix repository-wide Ruff, formatter, and mypy failures.
- Reconcile TODO evidence with current code.
- Classify generated root artifacts; preserve until founder approves cleanup.
- Create explicit clean baseline commit after review.

Exit: clean Git status and all declared repository gates pass.

### D1 — Packet and evidence completeness

Goal: ensure self-task approval binds exact packet and evidence.

- Persist packet version and digest.
- Reject approval/result against mismatched digest or base revision.
- Persist changed-file boundary evidence and exact gate evidence.
- Require separate review decision after execution.

Exit: mismatch, missing evidence, path escape, stale approval, and self-acceptance tests fail closed.

### D2 — One low-risk self-task

Goal: complete one documentation/test-only TODO item through live kernel.

- Founder approves frozen task.
- Worker leases task and creates isolated worktree.
- AGY implements only allowed files.
- Independent verifier reruns gates.
- Founder accepts or requests refinement.

Exit: accepted revision has complete task, attempt, evidence, review, and audit lineage. Source
merge remains separately approved.

### D3 — Staging control plane

Goal: move durable orchestration off local SQLite.

- Deploy Render web service with AGY execution disabled.
- Connect Supabase Postgres through pooled `DATABASE_URL`.
- Run Alembic upgrade and rollback proof in staging.
- Register outbound Mac worker and prove recovery.

Exit: remote control plane survives restart; Mac resumes exact checkpoint without duplicate work.

## First self-task selection rule

Choose task satisfying all:

- one module or documentation/test pair;
- low risk;
- no migration, deployment, network, secret, meeting, or call side effect;
- deterministic local gates under ten minutes;
- reversible isolated diff;
- independent reviewer can prove outcome.

Recommended first task: reconcile one bounded TODO subsection against executable tests, without
changing runtime behavior.

## Stop conditions

Stop and mark blocked when:

- repository or base revision changes after approval;
- AGY authentication/quota fails;
- worktree path or allowed-path validation fails;
- undeclared dependency/network/tool request occurs;
- gate output is missing, malformed, or contradictory;
- timeout or cancellation cannot terminate full process group;
- worker/control-plane identity changes;
- production side effect is requested before separate approval.
