# Astra engineering plan: trustworthy autonomy and research-first delivery

Prepared 5 September 2026 from the audit of local main `0238fcb84e335ca0cff346388242855ed7bc05e4` and Antigravity session `8f2a55c1-30ae-4bfc-bb2f-60759025fe13`.

Companion evidence: [engineering audit](ASTRA_ENGINEERING_AUDIT_2026-09-05.md).

Status: proposed implementation plan. No packet has been dispatched or approved by creating this file. “Astra” names the senior reviewer/planner role, not a new provider integration. The current canonical architecture file remains unchanged.

## Objective

Make AlphaBrain reliably choose, build, verify and maintain a suitable solution for a specified project. Success means the selected technology follows research and constraints, execution follows immutable scope, and completion follows trusted evidence.

Sequence:

```text
Restore review/gate/promotion integrity
    → unify lifecycle and identity
    → enforce isolated execution
    → introduce research and architecture contracts
    → compile approved design into project-specific tasks
    → prove three different project classes
    → operational soak, staged deployment and measured expansion
```

Do not expand federation or automatic production deployment while foundational acceptance checks can be bypassed.

## Target system design

### One authoritative control plane

Keep FastAPI, Pydantic and SQLAlchemy. Triage should become an admission view/service over the same task/attempt/approval lifecycle used by the kernel. Prefer adapting existing TaskEngine protections over duplicating them.

PostgreSQL owns shared project, task, lease, review, promotion and audit state. A local SQLite spool is an offline delivery buffer, not a second authoritative task queue. During migration, explicitly designate one write owner and reconcile legacy tasks; do not dual-dispatch both engines.

Use an outbox for dispatch/notification intents committed with state. Workers acknowledge idempotently. Retry side effects only under an explicit idempotency key or reconciliation policy. Do not promise global exactly-once execution across process/network failures.

### Explicit states and immutable references

Proposed project flow:

```text
INTAKE → RESEARCHING → DESIGN_REVIEW → SPEC_APPROVED
       → IMPLEMENTING → VERIFYING → INDEPENDENT_REVIEW
       → PROMOTION_APPROVED → PROMOTED → PREVIEW_ACCEPTED
       → RELEASE_APPROVED → RELEASED
```

`BLOCKED`, `FAILED`, `CANCELLED` and bounded repair transitions are explicit. None may be interpreted as success. Research can finish without code changes; implementation cannot claim success from an unchanged baseline unless its packet explicitly defines a valid no-change outcome.

Bind these identities throughout:

```text
project_id, repository_id, task_id, task_revision, attempt_id,
lease_id, fencing_epoch, specification_digest, research_digest,
architecture_digest, packet_digest, base_sha, result_sha,
gate_manifest_digest, reviewer_principal, promotion_id
```

Every relevant digest change invalidates old execution/review/promotion authority. Review approval is scoped to a particular result SHA and evidence set. Distinguish authentication of the reviewer from integrity hashes. Keep signing authority outside executor access if signatures are used.

### Roles and enforcement

- Founder owns product decisions, risk acceptance, spending and release authority.
- Research agent reads approved sources and writes research artifacts.
- Architect selects contracts and alternatives using those artifacts.
- Executor edits only its isolated checkout and cannot mint review/promotion evidence.
- Verifier runs trusted gate definitions and captures immutable artifacts.
- Reviewer reads frozen source/evidence without write or deployment capabilities.
- Promotion service checks authorization and atomically advances the approved target.

Run generated code under process/filesystem/network restrictions. Select containers/VMs for portable tasks and a appropriately isolated macOS execution account/VM for native tasks. No provider or cloud credentials should be mounted merely because tests run. A Git worktree remains useful for version control but does not provide these restrictions.

## Packet order and acceptance conditions

Each packet must have its own exact resolved base, allowed files, required tests and approval policy. Paths below are planning targets; inspect actual dependencies and obtain a bounded task envelope before dispatch. Never silently expand allowed paths after execution begins.

### A0 — Establish reliable baseline and documentation status

Purpose: make all parties inspect the same revision and stop recycling stale success claims.

- Record actual HEAD, source/lock hashes, current test results and skipped-test reasons.
- Fix current type/format failures in dedicated bounded packets, including real `TYPE_CHECK` defect.
- Align local and CI quality commands; reconcile dependency sources (`requirements.txt`, `pyproject.toml`, lockfile) in a separate mechanical packet.
- Rebuild graph against current source and save graph HEAD/hash; generate compact context.
- Record roadmap ID mapping. Old P9 specification intelligence and new P9 self-development are different scopes. Do not erase either backlog.

Accept: clean environment can install and run the same gates; no current mandatory static errors; required PostgreSQL job runs rather than silently skips. Documentation reports exact scope and date. Preserve historical evidence.

### A1 — Fail-closed reviewer invocation and terminal protocol

Targets: `alpha_worker/senior_review_engine.py`, focused tests under `testscript/`.

- Remove approval fallback for missing executable. Inject test provider explicitly.
- Return a typed invocation result with requested/resolved model, status, exit code, timeout and output artifact.
- Parse one exact structured terminal verdict; reject conflicting or malformed output.
- Nonzero exit, absent model, provider rejection and timeout produce blocked review.
- Make reviewer cwd/source snapshot explicit and read-only; no unconditional permission bypass.
- Do not replace unavailable diff with diff-stat and approve. Split large diffs into complete review chunks with coverage manifest rather than silent 25,000-character truncation.

Required regressions: missing AGY in production; rejection mentioning APPROVE; earlier approval followed by rejection; duplicate verdicts; nonzero exit containing approval; missing diff; incomplete chunk coverage; timeout; untrusted patch text mimicking instructions.

Accept: every case blocks, valid structured success works, no live model is called from tests, no review writes source. Artifact includes full reviewed SHA and evidence digest.

### A2 — Restore dispatcher and gate truth

Targets: `triage_dispatcher.py`, existing typed gate runner/protocol, conformance tests.

- Abort normal completion unless bridge result is typed success, including its QA/graph requirements.
- Preserve failed partial work as repair evidence; readiness/dispatch exceptions cannot fall through.
- Reject failed commit creation and non-resolved result SHA.
- Reuse shared typed acceptance runner; honor required gates, explicit gate types, timeouts and executable policy.
- Never infer gate type from an executable substring or silently replace missing commands with pytest.
- Revalidate final base-to-result changes after tests; bind gate evidence to tested source/lock hashes.

Required regressions: bridge completed=false with changed files; incomplete QA manifest; bridge unavailable; exception after partial write; commit returns None; missing required gate; duplicate/conflicting evidence; valid Mypy command; gate modifies source after earlier tests; committed out-of-scope change.

Accept: no partial/invalid attempt becomes completed. All production callers share equivalent acceptance rules.

### A3 — Trusted review identity and promotion

Targets: triage result routes, task-engine/promotion service, senior-review persistence, merge CLI, security tests.

- Worker result accepts executor-owned fields only. Reject reviewer/promotion fields supplied by executor.
- Bind task results to tenant, project, worker, attempt, lease ID and fencing epoch.
- Record review attestations from a authenticated, authorized distinct reviewer principal.
- Include result/base SHA, packet revision, gate manifest and expiry/revocation semantics.
- Before merge, compare approved result SHA against branch tip; lock target promotion and enforce expected current HEAD.
- Remove normal automation access to skip-review/force-approval bypass. Emergency recovery, if retained, needs distinct audited operator policy.
- Persist promotion success/failure and make repeated requests idempotent. Preserve dirty worktrees; cleanup cannot discard unknown user changes.

Required regressions: wrong-project worker; stolen/stale lease; self-review injection; missing signature/trusted identity; review for prior SHA; branch moved after review; concurrent promotions; dirty target; repeated merge; crash after Git operation before DB acknowledgment.

Accept: trusted service rejects all cases before mutation and can reconcile interrupted promotion. A local Git fixture exercises real merge behavior; subprocess mocks alone are insufficient.

### A4 — Canonical packets, bounded repair and correct DAG inputs

- Resolve immutable base SHA at admission. Stop accepting absent/partial hashes; explicitly version and migrate legacy envelopes.
- Add distinct verification/review/promotion states; dependents await the output state they actually require.
- Bind downstream checkout to promoted upstream artifacts, not merely parent queue `completed`.
- Separate task revision from attempt. New repair instructions create a traceable revision under an approved repair budget.
- Track total attempts, wall time, tokens and review rounds; operator retry does not erase lifetime consumption.
- For scope/risk growth, produce a new approval request before execution.

Required regressions: parent executed but not reviewed; parent rejected after execution; parent promoted into wrong repository; changed base during approval; missing hash; mutation of command with unchanged partial hash; retry storm; cycle/dangling dependency; fan-in/fan-out; crash/resume with fencing.

Accept: no child consumes unapproved/unavailable code and no infinite repair path exists. Property-based state tests should supplement normal examples.

### A5 — Execution containment and data permissions

- Implement actual resource and filesystem boundary for code execution and read-only reviewers.
- Give command broker typed capabilities; enforce tool arguments and working directories.
- Prevent writable shared runtime/config and protected Git metadata from task-controlled code.
- Limit CPU, memory, disk, runtime, child process trees and network egress; capture scrubbed logs.
- Test repository instructions, transcripts, retrieved pages and source comments as adversarial data.
- Check actual changed files/lines after execution, including nested directories, renames, symlinks, binary and already-committed changes.

Accept: disposable sandbox fixtures prove forbidden file read/write and unauthorized egress are denied before harm; process timeout reaps descendants; no credentials appear in artifacts. These tests must never target real home-directory secrets.

### A6 — Consolidate lifecycle, durable scheduling and operational recovery

- Migrate triage onto shared lifecycle or document/enforce a single-authority bridge.
- Persist review jobs and repair jobs so CLI supervisor disappearance does not abandon work.
- Make scheduler capacity-aware; durable idle, working, blocked and awaiting-owner states.
- Integrate worker liveness, lease reconciliation, encrypted spool and review queue.
- Keep Temporal optional pending ADR: prototype equivalent recovery scenarios against existing engine before choosing. Avoid operating duplicate retry systems.

Accept: restart control plane, worker and reviewer at each transition using disposable systems; reconcile results without duplicate promotion. Prove network outage, disk pressure, stale worker, lost response and task cancellation. Report actual work versus availability separately.

### R1 — Research and requirements contracts

Create versioned validated models for ProjectBrief, SourceEvidence, ResearchDossier, ArchitectureDecision and AcceptanceMatrix. Add draft/reviewed/approved states and content hashes; preserve links to source transcript/request.

Minimum ProjectBrief:

- user groups, problem and success outcomes;
- required devices, platforms and environments;
- functional scope, non-goals and important user journeys;
- data classes, tenancy, consent, residency and retention;
- integrations, native hardware APIs, offline/background requirements;
- performance, reliability, accessibility and recovery targets;
- deadline, budget, staffing/skills and operating constraints;
- assumptions, owner decisions and unresolved blockers.

SourceEvidence includes URL/title/publisher, retrieved timestamp, applicable version, supported claim, short evidence excerpt, confidence and content hash. Do not copy entire copyrighted pages into artifacts. Unavailable sources remain explicit gaps.

Accept: malformed lists/booleans/confidence fail schema validation; vague input cannot authorize coding; technical claims need relevant sources or explicit unresolved assumptions. A source link by itself does not validate the associated claim.

### R2 — Framework and build-versus-integrate decision engine

Require decision dossier before creating a new project or adding a major dependency. For a minor change in an existing system, reuse approved ADR unless changed constraints invalidate it.

Candidate evaluation must include:

1. Existing stack or simplest viable design.
2. At least two genuinely viable alternatives when alternatives exist.
3. Buy/integrate/open-source reuse option where relevant.
4. Hard constraint rejection first: platform capability, data rules, security, budget and team support.
5. Comparative evidence: maintenance, release history, license obligations, dependency footprint, compatibility, testability, migration cost, hosting, performance and lock-in.
6. A spike for the most consequential uncertainty, with predefined pass/fail criteria.
7. Decision, rejected alternatives, evidence and revisit triggers.

Illustrative scoring weights, adjusted per brief: functional/platform fit 30%; security/reliability 20%; team/delivery fit 15%; operating cost 15%; measured performance 10%; maintenance/exit cost 10%. Do not convert missing facts into confident scores or use GitHub stars as proof of suitability.

Examples:

- Offline hardware app: compare native, React Native and Flutter on actual device APIs and background behavior.
- Content-heavy website: compare static/content rendering with app framework; measure generated JavaScript and interaction needs.
- Authenticated SaaS: compare extending current FastAPI/web stack, integrated framework, and managed components using tenancy, operations and team knowledge.
- High-throughput service: benchmark workload and profile bottleneck before choosing Go/Rust or decomposing services.

Accept: “mobile app → Flutter” or “website → React” without documented constraints is rejected. Candidate technical details use primary, current documentation. No framework is a universal winner.

### R3 — Architecture package and design review before code

Require proportional artifacts:

```text
docs/requirements/brief.md
docs/requirements/approved-spec.md
docs/research/sources.json
docs/research/alternatives.md
docs/decisions/ADR-001.md
docs/architecture/system.md
docs/architecture/threat-model.md
docs/contracts/...
docs/qa/acceptance-matrix.md
docs/operations/runbook.md
```

Architecture must specify component ownership, runtime/deployment topology, schema/data migrations, API/events, authentication/authorization, concurrency, retries/idempotency, consistency, failure recovery, secrets, resource budgets, observability and rollback. UI projects add design tokens, interaction states, keyboard/accessibility, responsive layouts and asset provenance.

Review the design independently before implementation. If essential uncertainty survives, issue a research/spike packet, not a broad coding packet. Review size should follow risk; do not require a book for a two-line repair.

Accept: each major design decision traces to a requirement and evidence; every high-impact risk has a test or owner decision; no contradiction between architecture, task envelope and policy.

### R4 — Project-aware task compiler and verification profiles

Replace AlphaBrain-specific directory assumptions with project manifest/capability inspection. Derive valid paths and tools from actual repository and approved stack.

Compile vertical slices with dependency artifacts, implementation scope, exact gates and relevant context. Gate profiles can include Python, TypeScript/web, mobile/native and service/API suites. Select actual commands from project configuration; do not blindly impose pytest/Ruff on Flutter or a static site.

Every requirement maps to evidence type and executable test where possible. Keep independent verifier cases outside executor write scope. Include property/contract/browser/accessibility/performance/security checks as appropriate. A missing tool is blocked, not N/A.

Accept: web profile reproduces browser journeys; mobile profile uses actual target build/device proof; API profile exercises real database/authorization boundaries. Research-only tasks can complete by delivering approved artifacts without fabricated code changes.

### O1 — Quality, cost and operational telemetry

- Track trace IDs for project/task/attempt/review/promotion, token usage by provider response, queue latency, execution/review duration, retries, cost and escaped defects.
- Replace broad JSON scanning with bounded SQL aggregation and indexed queries where measurements justify it.
- Distinguish task execution completed, reviewed, promoted, deployed and user accepted.
- Generate founder/client views from verified state and redact internal/private data.
- Alert only on actionable stall, budget exhaustion, approval need or failed recovery; deduplicate calls/messages.
- Owner notification and release actions remain separately authorized.

Accept: metrics reconcile with sampled durable events; unavailable usage is unknown rather than zero; p95 latency/resource budgets hold under declared test load; no secrets or high-cardinality prompt content in telemetry.

### V1 — Prove capability across three bounded project classes

1. Existing internal feature repair with adversarial review cases and no manual state edits.
2. Small web/API product with authentication, persistence, responsive UI, browser E2E and preview acceptance.
3. A platform-constrained project requiring an actual technology choice and spike. Native/mobile only if the brief warrants it.

Use controlled fixture repositories under clientProjects; keep tests under their `testscript/` directories. Include interruption/recovery and at least one rejected design or implementation that is repaired correctly.

Accept: full chain from cited research to reviewed artifact and verified preview; no manufactured review, direct DB transition, ignored gate, silent skip, escaped scope, manual product patch, or unapproved deployment. Publish evidence dossier, not a universal “bug-free” claim.

## Prompt to give Antigravity supervisor

```text
You supervise AlphaBrain engineering work. Read ASTRA_ENGINEERING_AUDIT_2026-09-05.md
and ASTRA_RESEARCH_AND_AUTONOMY_EXECUTION_PLAN.md. Treat findings as hypotheses to
verify against current source, with reproduced cases already documented.

First capture current branch/HEAD, dirty state, task queue state, runtime and graph
freshness. Preserve user changes. Select only the next uncompleted bounded packet.
Use the existing AlphaBrain workflow for implementation as repository rules require.
Do not claim the current review engine is trustworthy merely because it returns
APPROVE: A1-A3 repair that exact boundary. Any bootstrap repair needs independently
collected evidence and founder-reviewed promotion until those controls are proven.

Before dispatch, produce a concrete packet: objective, non-goals, current base SHA,
allowed files, relevant findings, architecture constraints, acceptance criteria,
typed commands, negative cases, artifact locations, budget and stop conditions.
Resolve required test/doc paths before leasing. Never weaken policy to finish.

Use research/architecture review for consequential design decisions. Use current
primary sources and a project-specific alternatives matrix. Do not default from
"app" to Flutter or from "web" to one framework. Preserve an existing stack unless
evidence justifies replacement. Do not change the canonical Opus-owned document
without its authorized workflow; propose amendments in the packet.

Implement through isolated worker. Run deterministic gates first. Give reviewers
the frozen complete diff, specification and evidence. Reviewers produce independent
findings before reconciliation. Verify model availability and provenance; never
synthesize approval on an unavailable provider. Keep tokens bounded using task-local
context and fresh graph metadata, not repeated full conversation history.

On failure: retain exact sanitized evidence; isolate cause; add a regression case;
repair within scope and budget; rerun affected and mandatory release checks.
If scope or authority changes, stop dependent execution with a precise blocker.
Never directly edit queue status, suppress mandatory tests, relax assertions,
skip review, merge an unreviewed SHA, or count a stale graph as current evidence.

Stop report: packet ID, source/base/result SHA, changed files, tests and skips,
static gates, independently reproduced negative cases, artifacts/digests, remaining
findings, budget used, cleanup evidence, and next packet. No push/deploy/migration
unless separately authorized for the exact target. Documentation preparation does
not grant future execution or release approval.
```

## Per-packet implementation prompt template

```text
PACKET: <ID and objective>
BASE: <resolved current 40-character SHA>
REPOSITORY: <approved absolute path>
ALLOWED PATHS: <exact source/test/doc files>
NON-GOALS: <explicit exclusions>
FINDINGS: <audit finding IDs, source locations and reproduction>
DESIGN: <selected approach, contracts, failure states and alternatives rejected>
REQUIREMENTS: <numbered observable behaviors>
ACCEPTANCE: <positive and negative cases, independently verifiable>
GATES: <typed gate IDs, executable, argument array, timeout, required artifacts>
DEPENDENCIES: <required promoted commit/artifact hashes>
BUDGET: <attempt count, review rounds, wall time, spend/tokens, concurrency>
STOP: <blocked provider, missing permission, changed scope, exhausted budget>
HANDOFF: <frozen SHA, evidence manifest, review findings, remaining risk>
```

## Release exit criteria

- Acceptance is fail-closed across every entry point, not just one tested kernel.
- Required tests run; unavailable required integration infrastructure blocks release.
- Source, environment, gate evidence and review are bound to the promoted artifact.
- Executor cannot approve its own work or silently broaden permissions.
- Research and design are mandatory where they can materially change technology choice.
- At least the bounded proofs above succeed with realistic failure injection.
- Restoration, rollback and resource/cost budgets are demonstrated.
- Progress claims distinguish local, remote, staged, production, and user-accepted results.

Only then expand task difficulty, multi-project concurrency, unattended windows and deployment authority incrementally.
