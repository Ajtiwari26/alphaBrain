# AlphaBrain engineering audit — 5 September 2026

## Decision

AlphaBrain has demonstrated useful supervised self-development on real source code. It is not ready for unrestricted autonomous delivery of difficult client projects. The largest gaps are enforceable trust boundaries and research/architecture admission, rather than the choice of Python or the number of models.

Recommendation: continue supervised, isolated internal work; repair the blocking findings below before broadening automatic promotion or client access. This review does not authorize deployments, database mutations, or changes to the canonical architecture document.

## Scope and evidence quality

- Checkout: `/Users/ajaytiwari/Desktop/Projects/alphaBrain`, clean `main` at `0238fcb84e335ca0cff346388242855ed7bc05e4`, 73 commits ahead of its local `origin/main` reference. No fetch was performed, so remote parity was not established.
- Requested Antigravity session: `8f2a55c1-30ae-4bfc-bb2f-60759025fe13`. The session exists as a SQLite conversation database, with a corresponding artifact directory.
- Indexed all 19,637 stored steps. A generic read-only protobuf traversal found text fields in 9,601 payloads. Reviewed selected claims, recent execution records, architecture/review artifacts, current skill, source, and durable task results. This is a broad engineering audit with deep inspection of critical paths; it is not a claim that every opaque payload, nested subagent conversation, or source line was exhaustively reviewed.
- Read-only database access used immutable SQLite URIs because ordinary read-only access failed. The inspected conversation had no sidecar WAL listed; queue results are a snapshot, not a continuing monitor.
- Existing code-review graph was consulted through its database because no graph MCP tool was available. Its metadata points to `37cb6602...` on `alpha/h4-result-promotion`, last updated 31 August. No relevant new triage/review nodes were found. It is unsuitable as current context for P9 without rebuilding.
- Verification: full local pytest; Ruff lint/format checks; Mypy; source tracing; isolated in-memory probes of approval and dispatch. No AGY model was invoked, no task approved, no code repaired, no branches merged, and no remote service changed.
- Meeting media, telephony, live cloud recovery, malicious-code OS containment, and production load were not exercised in this audit.

## What the session really achieved

The session demonstrates substantive progress, including feedback-driven repairs and real Git changes. Recent claims are corroborated by four completed local queue records:

| Task | Work product | Recorded result commit | Review record |
|---|---|---|---|
| `tsk_eva_f9be4de99e4b` | Audit export CLI | `31d7c90a1fa7dfaef984f8ae221364694969bad0` | Separate session review artifacts exist; current queue row lacks a senior-review approval object |
| `tsk_eva_bbf9a76143fd` | DAG dependency engine | `3b192d87e0b4c34c32394554852d563746e017a7` | Pro approval and Opus final approval stored |
| `tsk_eva_0a85fb05fd52` | Provenance telemetry | `dbf9d1577c312443371a4a6e9ba01d4ecc12e2f8` | Pro approval and Opus final approval stored |
| `tsk_eva_bd6ae086ece8` | Pipeline metrics CLI | `0238fcb84e335ca0cff346388242855ed7bc05e4` | Pro approval and Opus final approval stored |

All four envelopes use `base_commit: HEAD` and require only `unit_test` and `lint`. Their existence proves useful execution and review activity, not immutable, independently secured attestations.

Recent session anchors:

- Step 19572 reports telemetry task merged and 634 passing tests.
- Step 19584 admits a dependent metrics task; step 19602 reports its code delivered.
- Step 19624 reports metrics task reviewed and merged.
- Step 19636 calls the complete DAG pipeline “100% autonomously” completed.

The supervisor still issues admission, review, approval, worker-cycle, senior-review, and merge commands. That is supervised pipeline operation. It does not demonstrate an autonomous product manager choosing and completing an entire roadmap.

At inspection: `launchd` listed worker PID 1356. Queue had four completed tasks and no pending/approved/executing tasks. Worker availability is established; active development is not occurring in that queue at this snapshot. The normal daemon has no triage/senior-review integration found by source search, while the demonstrated P9 path uses separate CLI cycles.

## Independent quality results

| Check | Result | Interpretation |
|---|---|---|
| Full pytest | 637 passed, 11 skipped, 2 warnings; 51.11 seconds | Existing tests pass |
| Ruff lint | Pass | No current configured lint violations |
| Ruff format | 5 files need formatting; 205 already formatted | Formatting gate fails |
| Mypy | 10 errors in 4 files, 74 source files checked | Type gate fails |
| PostgreSQL proofs | Skipped without Docker | Not re-proven in this run |
| Daemon submit test | Skipped for known global-logging flakiness | Known test-isolation debt |
| Read-only adversarial probes | Multiple unsafe acceptance paths reproduced | Test count does not certify boundaries |

Mypy errors include nonexistent `GateType.TYPE_CHECK` in `triage_dispatcher.py:161`, `Any` return types, event payload typing, and metrics dictionary inference. The enum error is a runtime failure when a Mypy acceptance command is encountered, not merely a cosmetic type annotation.

## Engineering findings

Severity describes impact in the current authorized-worker/supervisor threat model. Code-observed findings are distinguished from locally reproduced ones. None claims remote exploitation occurred.

### F01 — Critical: missing reviewer executable synthesizes approval

`alpha_worker/senior_review_engine.py:113` returns approval text when `ENV == test` **or** the AGY binary is absent. An in-memory probe with production settings and a nonexistent binary returned `VERDICT: APPROVE`.

Failure mode: review infrastructure disappears and the review gate succeeds. Remove production fallback; test doubles must be dependency-injected and unavailable to production. Missing executable, timeout, authentication failure, quota exhaustion, or nonzero exit must block review.

### F02 — Critical: rejection text can be accepted as approval

`senior_review_engine.py:180,203` uses substring matching. Both probes returned true:

- Pro text: `Do not APPROVE. VERDICT: REJECT`.
- Opus text: `Earlier FINAL_APPROVAL was incorrect. VERDICT: REJECT`.

`_invoke_agy` also returns output on nonzero exit. Use one strictly parsed terminal verdict, validate process success separately, reject conflicts and missing fields, and bind the verdict to exact task revision and commit. Diff text is untrusted content and can contain apparent instructions or verdicts.

### F03 — Critical: rejected AGY execution can still complete triage

`alpha_worker/triage_dispatcher.py:292–321` logs `dispatch_res.completed` without enforcing it, catches execution errors and continues, and proceeds when bridge readiness fails. With only mocks, an agent result of `completed=False` plus a changed file and passing gates caused `queue.complete_task` to execute.

The live bridge contains useful terminal/QA-manifest checks, but this caller discards their rejection. Require a successful typed dispatch outcome before any result acceptance. Partial files after failure are repair evidence, never proof of completion.

### F04 — High: commit failure becomes apparent completion

`triage_dispatcher.py:366–368` substitutes `base_commit` if commit creation fails. Probe produced a completed result with `head_commit: HEAD` after mocked commit failure. Require a real resolved object ID and verified work product; commit failure must preserve evidence and block.

### F05 — Critical: promotion trusts mutable booleans and branch names

`alpha_core/triage_cli.py:595–685` checks `gates_passed` and `senior_review.approved`, then merges a branch by name. It does not compare the current branch tip against the reviewed result SHA. `--skip-senior-review` bypasses review, and an existing test explicitly expects that bypass to succeed.

`TaskTriageQueue.record_senior_review` (`triage_queue.py:613`) stores ordinary JSON. It does not sign a commit-bound attestation. Calling that record “cryptographic certification” overstates its implementation. A hash also does not establish reviewer identity.

Require a trusted review principal, task/attempt/spec/gate/commit binding, immutable artifacts, branch-tip comparison under promotion lock, and a durable promotion record. Local administrator access remains a separate trust boundary; do not claim protection against a host administrator rewriting its own database.

### F06 — Critical: triage API result admission is weaker than the original kernel

`alpha_core/api/app.py:2365–2432` accepts founder/admin/worker roles, leases without worker ownership binding, and accepts a free-form result dictionary. It passes that dictionary into `complete_task` without validating typed gate coverage, reviewer-only fields, attempt identity, lease fencing, or project scope in these handlers.

This is a code-observed boundary gap; a remote exploit was not attempted. Reuse the stronger original TaskEngine contracts instead of maintaining a second acceptance system. An authenticated executor must never be able to supply trusted `senior_review` approval in its own result.

### F07 — High: required gates and declared types are not enforced

`triage_dispatcher.py:133–184` executes commands but ignores `required_gates`, infers gate type from executable name, and defaults to pytest when commands are absent. Probe: required security evidence missing, one passing Ruff command present, aggregate accepted.

`EvaTaskProposer` always builds pytest plus Ruff. It explicitly excludes `typecheck` from additional commands and never adds a type-check gate. Consequently, requested quality can be silently reduced. Resolve gates from project capabilities and risk; retain every required gate or block before leasing.

### F08 — High: a Git worktree is not a security sandbox

`alpha_core/config.py:158` defaults unattended permissions to true; `antigravity_live.py:814` adds `--dangerously-skip-permissions`; the senior reviewer uses that flag unconditionally. Review subprocesses do not set an isolated review cwd. Worktree cwd and later Git diff checks do not prevent reads/writes elsewhere, network access, credential access, or child processes.

The session's plan explicitly introduced this bypass. Reviewers and executors need enforced process/filesystem/network capabilities with minimal credentials. Keep review read-only. Tests that prove worktree paths cannot prove OS isolation.

### F09 — High: mutable execution base and incomplete digest compatibility

Admission uses `HEAD` (`triage_cli.py:508`). Dispatcher allows legacy and partial Eva hash fallbacks (`triage_dispatcher.py:259–279`), and skips comparison entirely for a missing stored hash. Eva fallback hashes only title, criteria and allowed paths, leaving other execution-sensitive fields outside that compatibility hash.

Resolve base SHA before approval. Hash a versioned canonical packet covering repository identity, spec, scope, gates, commands, capabilities, budget and base. Migrate old packets explicitly; do not retain permissive compatibility indefinitely.

### F10 — High: dependency completion occurs before review/promotion

`lease_next_approved_task` (`triage_queue.py:470`) releases dependents when upstream status is completed. `complete_task` sets that status before senior review or merge. A dependent can start while its parent is rejected or not present in its base checkout.

Existing DAG test deliberately completes a parent directly and then leases a child. It proves queue ordering, not verified dependency delivery. Add promoted/artifact-ready states and bind downstream inputs to exact upstream commits. Separate research artifacts from code dependencies.

### F11 — High: scope checks do not enforce the advertised blast radius

`SafetyGate.evaluate_envelope` counts `allowed_paths` entries, not changed files (`gate.py:326`). A directory is one entry but may contain hundreds of files. The triage result path does not measure the advertised 500-line limit. It inspects working-tree status before gates; it does not revalidate the final committed diff after tests or account comprehensively for commits created by AGY.

Inspect base-to-result changes plus untracked/staged modifications, renames, binary files and symlinks. Recheck after gates, freeze artifacts, and enforce file/line budgets on actual changes.

### F12 — High: repair budget and truthful state remain inconsistent

`queue_task_for_senior_repair` changes completed to approved and rewrites instructions/hash without incrementing a distinct bounded review-repair budget. `retry_task` resets retry count. This can defeat a advertised finite retry ceiling across supervisor-issued cycles. Preserve append-only attempts and cumulative budgets; require a new bounded grant when exhausted.

The legacy `SDLCWorkflowRunner.run` auto-approves specification and preview and declares `DEPLOYED` without waiting for verified delivery. `SDLCActivities.extract_specification` returns hardcoded content. These were inspected as demo-like code, not proven active production routes. Exclude them from production claims and entry points until replaced.

### F13 — High product gap: research-first architecture is advisory, not enforced

`alpha_core/eva/spec_extractor.py` produces title, summary, requirements, criteria and paths. Its prompt hardcodes AlphaBrain directories. It has no source ledger, alternatives comparison, constraints matrix, benchmark evidence, decision record, license review, or research approval state.

The custom SDLC skill contains sensible discovery, architecture, security and QA instructions. It says to inspect current docs for unstable APIs, but does not require a sourced technology-selection dossier. No dedicated research/ADR/stack benchmark document was found in the inspected `docs` inventory. Manual supervisor discussions do not establish a mandatory runtime research workflow.

Also: extractor parsing coerces booleans, lists and floats without a strict complete schema; a string `"false"` is truthy in Python. Model-generated paths and risk cannot authorize capabilities.

### F14 — Medium/high: observability and evidence descriptions overstate coverage

Latest metrics CLI scans `list_tasks(limit=100000)` and calculates summaries in memory. Four rows are a useful smoke test, not a scale benchmark. Histories and review details remain mutable JSON; graph metadata is stale; CLI provenance hardcodes extraction model and confidence even when extraction uses another path.

New metrics/provenance commits are real progress, but P9.7 should not be marked operationally complete without measured telemetry, alerts, persistent repair states, restart reconciliation, and soak evidence.

## Assessment by engineering function

| Perspective | Good foundation | Required improvement |
|---|---|---|
| Product/CTO | Requirements and approval concepts; real internal feature delivery | Customer constraints, ambiguous requirements, outcomes, architecture alternatives, feasibility experiments |
| Architecture | Modular control plane, worker, protocol, adapters | One authoritative lifecycle; immutable inputs; reconcile legacy/new P9 definitions |
| Security | Auth roles, command scans, path limits, original kernel approvals | Enforced sandbox, tenant/lease ownership, trusted evidence, prompt-injection resistance, review identity |
| Backend | FastAPI, Pydantic, SQLAlchemy, SQLite/Postgres support | Shared acceptance service, transaction-bound promotion, integration proofs and strict schemas |
| QA | Hundreds of tests; real repairs from model review | Independently authored negative cases, non-skippable release gates, real Git/process tests, browser contracts |
| SRE | launchd, encrypted spool, health, watchdog work | Current path integration, restore/soak/chaos tests, alerts, SLOs and bounded resource usage |
| UX/client delivery | Meeting implementation and transcript functionality | Real mobile/browser journeys, accessibility, consent, support/portal/product acceptance |
| Cost/performance | Roles and existing code graph | Measured cost per accepted task, fresh scoped context, short reports, bounded review depth |

## Technology recommendations

Keep the current Python/FastAPI/Pydantic/SQLAlchemy foundation. A rewrite will not fix boolean trust, loose parsing, or missing acceptance checks. Split large API/CLI modules by responsibility after correctness tests exist. FastAPI supports appropriate async I/O, while blocking work must be placed deliberately; SQLAlchemy requires care with per-task async sessions. [FastAPI concurrency](https://fastapi.tiangolo.com/async/), [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).

Use PostgreSQL as shared control-plane truth when coordinating remote workers; retain SQLite for local cache/spool or a deliberately single-host deployment. WAL supports local concurrency but has a single writer and is not a network filesystem strategy. SQL row locking can support queue consumers, but ownership, fencing and idempotency are still application responsibilities. [SQLite WAL](https://www.sqlite.org/wal.html), [PostgreSQL SELECT](https://www.postgresql.org/docs/current/sql-select.html).

Do not add Redis simply because queues exist. Introduce it only for a measured cache/rate-limit/ephemeral distribution need. Choose between improving the existing durable state engine and a bounded Temporal prototype using requirements for long-running, multi-service recovery. Merely depending on Temporal does not make existing workflows durable. Activities still need idempotency. [Temporal activities](https://docs.temporal.io/activities).

Render free hosting is useful for staging, but its documented sleep and resource constraints cannot substantiate a 24/7 orchestration promise. Select hosting against explicit availability and recovery targets. [Render free services](https://render.com/docs/free).

Candidate open-source tools, adopted only after a scoped compatibility/license check:

| Need | Candidate | Adoption condition |
|---|---|---|
| Browser behavior | Playwright | Real journeys and persisted state, not page-open checks; [assertions](https://playwright.dev/docs/test-assertions) |
| State-machine adversarial tests | Hypothesis | Generated retry/order/failure sequences; [documentation](https://hypothesis.readthedocs.io/en/latest/) |
| API boundary fuzzing | Schemathesis | OpenAPI-derived valid/invalid and authorization cases; [documentation](https://schemathesis.readthedocs.io/en/stable/) |
| Load and soak | k6 | Defined SLOs and representative workloads; [documentation](https://grafana.com/docs/k6/latest/) |
| Dependency vulnerability checks | OSV-Scanner | Scan resolved dependencies; triage exploitability and remediate; [documentation](https://google.github.io/osv-scanner/) |
| Traces, metrics, logs | OpenTelemetry | Correlate project/task/attempt/gate without recording secrets; [signals](https://opentelemetry.io/docs/concepts/signals/) |
| Reproducible Python environments | uv | Reconcile manifest/requirements/lock and verify clean sync; [sync semantics](https://docs.astral.sh/uv/concepts/projects/sync/) |
| Security requirements | OWASP ASVS | Select applicable versioned controls and map to tests; [ASVS](https://owasp.org/www-project-application-security-verification-standard/) |
| Build/review provenance design | SLSA/in-toto concepts | Bind output to inputs and trusted producer; no certification claim; [provenance](https://slsa.dev/spec/v1.2/provenance) |

Treat transcripts, retrieved pages, source comments and model reviews as untrusted input. Prompt instructions alone are insufficient containment. [OWASP prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).

## What a senior research workflow must add

Before selecting a framework, AlphaBrain must record users, devices, accessibility, network/offline behavior, integrations, data sensitivity, expected load, latency, budget, deadline, team skills, hosting and migration constraints. Explicitly distinguish facts, assumptions and unresolved questions.

Then compare retaining the existing stack, at least two credible alternatives, and a buy/integrate option when applicable. Evaluate mandatory constraints first; weighted scores are decision aids, not evidence. Cite primary documentation with version/date, record license/maintenance risk, and run a bounded spike for the highest uncertainty.

Examples of decisions rather than defaults:

- A content site may suit Astro or server-rendered pages; an interactive portal may justify an application framework. Content-heavy and app-heavy requirements differ. [Astro rationale](https://docs.astro.build/en/concepts/why-astro/).
- A web product needing server/client rendering and caching may evaluate Next.js, including operational caching implications. [Next.js caching](https://nextjs.org/docs/app/getting-started/caching).
- An “app” request must not imply Flutter. Compare web/PWA, React Native, Flutter and native Swift/Kotlin using device APIs, background behavior, UX, offline state and actual target-device tests. Flutter has a distinct rendering/platform architecture; React Native includes platform-specific code paths. [Flutter architecture](https://docs.flutter.dev/resources/architectural-overview), [React Native platform code](https://reactnative.dev/docs/platform-specific-code).

The selected design must include an ADR, data model, API/event contracts, trust boundaries, failure/recovery model, threat analysis, performance budgets and requirement-to-test traceability. Tasks should be compiled from this approved design, not from model enthusiasm.

## Model and token strategy

Use Astra/Opus for material architectural or security uncertainty; Pro for implementation and targeted review; Flash for mechanical work. Validate actual model availability and log requested/resolved identity. Do not infer competence solely from a model label or route work merely to consume expiring quotas.

Have reviewers first inspect the same frozen artifact independently; reconcile findings afterward. Current sequential debate exposes the second reviewer to the first one's conclusion and is not independent blind review. Neither reviewer should write implementation files or access deployment credentials.

For each task send only approved objective, changed contracts, fresh dependency subgraph, exact files, acceptance plan and relevant failure evidence. Reference immutable artifacts for expansion. Cache context by source hash. Rebuild stale graph data before use; a graph is navigation context, not a replacement for specifications or trusted evidence.

Measure tokens, elapsed time, retries, accepted changes, escaped defects and cost per accepted task. Reserve expensive review for risk, not for every wording change. Run cheap deterministic checks before models; never run costly review over known failing gates.

## Completion standard

The next honest milestone is: a constrained project can pass research, architecture approval, isolated implementation, independent evidence verification, reviewed promotion, preview acceptance and restart recovery without manual state edits or hidden bypasses.

Four internal tasks are encouraging evidence. They do not establish universal framework judgment, complex product completeness, bug freedom, production security, or autonomous business judgment. The companion execution plan defines how to earn those claims incrementally.
