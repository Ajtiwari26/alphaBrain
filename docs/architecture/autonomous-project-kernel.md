# AlphaBrain Autonomous Project Kernel

## Decision

First product target is not full meeting, calling, portal, or deployment platform. It is a
supervised autonomous delivery kernel that can complete one small software project safely, then
use that same kernel to complete AlphaBrain's remaining implementation backlog.

AlphaBrain supervisor owns scope, task graph, policy, acceptance gates, and final status.
Antigravity is an implementation worker. It must not invent roadmap, completion criteria, or
production side effects.

## Minimum complete loop

```text
Founder brief
  -> frozen task graph
  -> policy/approval check
  -> P5 Mac worker leases one task
  -> P6 AGY executes in isolated worktree
  -> worker returns process result, diff, artifacts, and declared gates
  -> evidence broker verifies required gates
  -> preview deployment or local preview evidence
  -> founder accepts, rejects, or requests refinement
```

No transition may be inferred from model text, a quiet process, or a preview URL alone.

## Required system contracts

1. `Project`: organization-scoped project, source repository, base revision, approved brief.
2. `Task`: exact project ID, worktree, input artifact hashes, dependency IDs, risk class,
   acceptance gates, and idempotency key.
3. `ExecutionAttempt`: AGY conversation ID, model, command PID/exit status, timestamps,
   changed files, stdout/stderr locations, and retry lineage.
4. `Evidence`: typed lint, test, build, browser, review, security, and preview records. Every
   evidence item includes producer, command, timestamp, artifact hash, and pass/fail status.
5. `Decision`: founder approval/rejection/refinement against exact task/spec/evidence version.

## State machine

```text
BRIEFED -> PLANNED -> WAITING_APPROVAL -> QUEUED -> LEASED -> EXECUTING
-> VERIFYING -> WAITING_REVIEW -> ACCEPTED
                             -> REFINEMENT_QUEUED
                             -> BLOCKED | FAILED | CANCELLED | SUPERSEDED
```

Only supervisor-controlled transitions may enter `QUEUED`, `VERIFYING`, `ACCEPTED`, or a
production deployment path. Worker can report, never self-accept.

## Implementation packets

### Packet A — Control-plane truth layer (P4 subset)

Implement task-ID integrity, append-only scrubbed events, checkpointed task progress, typed gate
evidence, no-evidence failure, and founder-only decision endpoints.

Exit proof: duplicate, mismatched, stale, and missing-evidence submissions fail; legal task has
auditable lifecycle record.

### Packet B — AGY execution adapter (P6 subset)

Implement one production-shaped `AgyAdapter` only. Input is frozen task envelope; output is a
structured execution result. It must create a safe worktree, resume/create project conversation,
stream progress, enforce timeout/cancellation, capture exit status, inspect changed-file boundary,
and return artifacts. It cannot approve itself or escape allowed paths.

Exit proof: seeded small repository receives one task, AGY changes only allowed files, process
result and evidence persist, timeout/nonzero exit become failure states.

### Packet C — One autonomous local project

Create a new client-project directory outside AlphaBrain. Use a compact project brief such as a
scientific calculator. AlphaBrain must create its own DAG, send tasks through Packet B, run
declared QA, and produce a local preview plus evidence report. Founder review is manual.

Exit proof: no direct human coding occurs inside client project after brief; every change is tied
to task, attempt, evidence, and review decision.

### Packet D — AlphaBrain self-development mode

Convert one remaining AlphaBrain TODO item into a project-scoped task using same kernel. Start
with low-risk test/documentation or isolated adapter work. Supervisor reviews every task packet;
only then widen to P7-P13.

Exit proof: AlphaBrain completes one of its own TODO items through its own task/evidence loop,
without claiming success before independent gates pass.

#### Self-development admission

Before a self-task is created, AlphaBrain performs a read-only admission check: source repository
must sit below an allowed root, be a clean Git worktree, resolve an immutable base commit, have a
founder identity and approval, use low risk, and list safe nonempty allowed paths. A dirty source
is rejected. AlphaBrain must never silently commit, stash, clean, clone, snapshot, or merge that
source. Founder may later explicitly request a clean-base commit or a separate immutable-snapshot
workflow; those are different approvals.

## Deferred until kernel works

- Full Unifold meeting product and Eva specification intelligence (P8/P9).
- AgentLine client/founder calls (P10).
- Client portal (P11).
- Production deployment automation and public side effects (P12).
- Temporal migration, privacy/pilot hardening (P7/P13).

These remain roadmap work, not prerequisites for first autonomous project completion.

## Supervisor operating rules

1. Supervisor writes brief, task graph, allowed paths/tools, gates, and risk before dispatch.
2. Antigravity receives one bounded implementation packet, never a vague phase instruction.
3. Supervisor independently runs selected gates and reviews evidence before task acceptance.
4. Failure produces a blocked/retry/refinement task, not an optimistic completion state.
5. Worker remains outbound-only; GUI, browser, calls, payments, credentials, production deploy,
   and destructive actions require explicit policy and human approval.

## First capability milestone

AlphaBrain can accept a manual project brief, create and execute a bounded AGY task in a separate
client-project worktree, verify it, show local preview/evidence, and accept or refine it. When
this milestone passes, use the same loop to complete AlphaBrain TODO work one packet at a time.
