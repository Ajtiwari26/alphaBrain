# AlphaBrain consolidated engineering review

Date: 2026-09-08
Audited revision: `062cf69bc8bc12fe3569b6a7e95448df2de032fa`
Verdict: **REPAIR_REQUIRED — reject full-completion and production-readiness claims.**

This is a risk-focused source review with independent local gates and narrow diagnostic probes, not certification that every possible defect has been found. No application code, remote service, database, deployment, or branch promotion was changed during this review. This report is the only repository addition.

## Verified progress and limits

- Independent `pytest --runxfail -q -p no:cacheprovider testscript/`: **797 passed, 11 skipped, 3 warnings in 63.12 seconds**. Skipped tests remain unproven; this is not a zero-skip run.
- Ruff check passed; Ruff format reported **244 files formatted**; mypy passed for **82 source files**.
- Checkout was clean before this report. Healing, portal, and provider adapter modules exist.
- Promotion now contains ancestry validation and a compare-and-swap ref update. Those improvements do not protect all recovery paths.
- No AlphaMeet changes were listed by `git diff --name-only b519af8..HEAD -- alpha_meet/`. The submitted report's `alphaBrain/alpha_meet/` path was not the correct repository-relative audit path.
- No live provider deployment, migration, client browser journey, or unattended repair cycle was executed by this audit. Do not turn mocked provider tests into live claims.

## Findings

### F01 — P1: Promotion recovery can discard unrelated work

Locations: `alpha_core/triage_cli.py:902`, `:928`, `:933`, `:1053`.

The APPLIED recovery path checks out main and runs `git reset --hard result_sha`. It does not first prove that main still points to that result or that the destination checkout is clean. If main advances after the original operation, recovery can rewind those commits. Uncommitted tracked edits can also be discarded. The normal promotion path contains another hard reset. FINALIZED returns success without reconciling current Git state.

Fix: validate destination cleanliness, operation identity, expected refs and worktree state under the promotion lock. Refuse divergent or ambiguous recovery. Never repair a journal by rewinding unrelated work. A historical completed operation may return historical success, but must not claim that the current checkout still equals its result without checking.

Acceptance: disposable Git repositories only. Force a crash at each journal/ref boundary; then introduce a later commit, dirty tracked file, or unrelated worktree change. Recovery must preserve each byte and commit, make no destructive mutation, and return an explicit conflict. Test repeated successful recovery and concurrent promotion too.

### F02 — P1: Portal overview ignores client project scope

Location: `alpha_core/api/app.py:2521`.

The route accepts `audit:read` and calls global `queue.get_stats()` without a project filter. CLIENT has that permission. A direct route probe with a client scoped to project A returned the stubbed global totals; the queue call had no arguments. This proves the missing scope filter, not a live cross-tenant database extraction.

Fix: scope database aggregation to authorized projects; apply an explicit client response allowlist. Test with real local records for two tenants and prove project B cannot affect A's totals.

### F03 — P1: Trace authorization and redaction are incomplete

Location: `alpha_core/api/app.py:2531`.

Project access is checked only if the task envelope contains a truthy project ID. Missing ownership skips that check. The response also returns raw provenance, unlike an explicit client-safe representation. Provenance can contain internal identity and lease metadata.

Fix: fail closed on missing ownership and use separate founder/client response schemas. Test absent ownership, foreign ownership, nested metadata and unknown future fields. Do not rely solely on secret-looking string replacement.

### F04 — P1: Repair generation expands approved scope

Location: `alpha_core/healing/repair_synthesizer.py:9`.

`bound_allowed_paths` unions original paths with every failure filename. A direct probe accepted `../outside.py` and `alpha_core/security.py` when the original scope was only `src/`. Test/log text is not authorization. The new task starts PENDING_REVIEW, so this is not evidence that execution already bypasses approval; it is evidence that the synthesizer does not preserve its claimed bounded scope.

Fix: preserve approved scope. Normalize and reject traversal, absolute escapes and symlink escapes at the responsible filesystem boundary. Represent needed expansion separately, requiring a new immutable packet and approval.

### F05 — P1: Healing limits reset across children and restarts

Locations: `alpha_worker/ci_healing_daemon.py:20`, `:28`, `:117`, `:163`; `testscript/test_healing_daemon_e2e.py:63`.

Circuit breakers are in-memory and keyed by each task ID. Every repair child gets another ID and fresh budget; restart loses all counters. Probes of a root and successive repair children each yielded attempt 1. The E2E test patches `get_circuit_breaker` to introduce lineage grouping absent from production, masking the defect.

Fix: persist root-lineage identity, attempt/signature counts, next eligible time and terminal escalation. Atomically reserve a repair attempt before dispatch. Enforce backoff in the actual scheduler, not only a helper.

Acceptance: unmodified production grouping; repeated identical failures across children; daemon restart; concurrent schedulers; changed signatures; exact budget edge; eventual escalation without another child. Test doubles may simulate model/network output, not replace the invariant being tested.

### F06 — P1: Healing can stall or drop recoverable work

Location: `alpha_worker/ci_healing_daemon.py:33`.

Review and merge subprocesses have no timeout. Nonzero review, malformed output and failed merge are added to `processed_tasks`, suppressing further attempts for that daemon lifetime. A hung child blocks the loop. Global task scans are not filtered by the configured project ID.

Fix: bounded subprocesses with process-group cleanup; durable, classified retry state; project-scoped scans; deterministic repository cwd and controlled environment. Recheck emergency stop and authorization before irreversible actions. Never retry an explicit rejection as if it were a transport failure.

Acceptance: hung child, transient provider outage, invalid response, explicit rejection, merge conflict, restart and foreign-project task. No lost work, leaked process or unintended project operation.

### F07 — P1: Supersession exposes a runnable intermediate state

Locations: `alpha_worker/ci_healing_daemon.py:122`, `:175`.

The daemon calls `retry_task` and then `reject_task` separately to escalate or supersede a failed task. Retry makes the parent APPROVED before rejection, creating a lease race.

Fix: one transactional supersede/escalate operation with expected-state checks, audit record and child linkage. Force worker lease overlap between the former two steps; the parent must never become executable.

### F08 — P2: Portal stream is a heartbeat, not a live tracker

Locations: `alpha_core/api/app.py:2566–2591`; `alpha_portal/portal.js`.

SSE emits empty heartbeats only. Tokens use the generic `portal-stream` scope without project/principal binding. UI fetches a trace once, defaults state from provenance to `in_progress`, uses a fallback `test-token`, and closes its event source on errors. This does not prove authenticated, live project progress. The current heartbeat stream contains no project data; generic tokens become a tenant risk if real events are added unchanged.

Fix: real task-state/event contract, scoped stream tokens, durable cursor/reconnect semantics, token refresh and actual authentication. Browser-test transitions, offline recovery and tenant rejection through the backend, not a mocked UI state.

### F09 — P1: Render preview is not bound to the reviewed artifact

Location: `alpha_worker/adapters/render_adapter.py:73`.

`deploy_preview` ignores its worktree argument and posts to the configured service's deploy endpoint without an explicit reviewed commit or preview-target validation. A method name does not prevent the configured service from being production.

Fix: deployment requires an approved packet binding provider, environment, exact artifact/commit and target service. Reject production targets in preview mode. Independently confirm provider-reported deployed revision. No live deployment is authorized by this repair plan.

### F10 — P2: P12 integration and migration capability are incomplete

Locations: `alpha_worker/adapters/supabase_adapter.py`; `alpha_worker/adapters/vercel_adapter.py:47`, `:95`.

The Supabase adapter exposes health, DDL validation and migration status; it has no migration execution/rollback implementation. Searches in alpha_core/alpha_worker found adapter class declarations but no consumers of these three new provider adapter classes. Vercel's subprocess `communicate()` calls are unbounded, so the polling deadline cannot bound a hung CLI.

Fix: first define and wire the approved deployment workflow. Implement explicit operator-approved migration planning/execution with tested recovery semantics, or label it planned rather than completed. Bound CLI lifetime and cleanup. Use disposable local infrastructure for migration proofs; provider writes require separate target-specific approval.

## Consolidated execution plan for Antigravity

Treat this document as the repair backlog, not permission to merge, push, migrate or deploy. Confirm current HEAD and dirty-path ownership before work; these line numbers refer to the audited revision.

1. **R-A: Promotion safety** — F01. Highest priority because recovery can destroy work. Design and adversarial temporary-repository tests first.
2. **R-B: Tenant boundary** — F02/F03. Fix backend scoping before extending portal data exposure.
3. **R-C: Durable healing** — F04–F07. Specify a persisted lineage state machine and atomic transitions before implementation. Include duplicate dispatch, restart and authorization boundaries.
4. **R-D: Real portal** — F08. Build on R-B with backend-to-browser proof.
5. **R-E: Delivery workflow** — F09/F10. Exact artifact/environment authorization, runtime integration, bounded execution and disposable migration proof. Keep live deployment separately approved.
6. **R-F: Final truth audit** — rerun all gates, explain every skip, demonstrate one bounded project lifecycle and one failed-repair/restart lifecycle using the real pipeline. Correct TODO, README and milestone seal to distinguish implemented, locally proven, live proven and planned capabilities.

For each packet, the senior defines contracts, failure modes, allowed paths and acceptance tests; implementation then follows that fixed scope. An independent reviewer inspects the exact candidate checkout and evidence. Model names or unanimous verdicts do not substitute for execution evidence.

### Mandatory stop and rejection rules

- No gate bypass, manual database status promotion, default signing secret, disabled authorization or hidden permission bypass.
- No test that patches the missing production invariant into existence. Preserve genuine regression assertions; justify skips individually.
- No scope expansion disguised as a helpful repair. Request an amended packet before touching additional files.
- Keep scripts/evidence under testscript and documents under docs. Preserve user work; do not delete unexplained artifacts or modify AlphaMeet.
- Bind reviews to exact task, base, result, scope and evidence. Re-review after candidate changes.
- Run focused regressions, full pytest with `--runxfail`, Ruff, format, mypy, committed-range and working-tree diff checks. Report actual exit codes, counts and skipped reasons.
- Stop locally with candidate SHA, changed files, evidence paths, residual risks and acceptance decision. Obtain explicit authorization for promotion and any remote operation.

Completion target: demonstrated safe behavior through the real pipeline, not a larger test count or a new zero-defect seal. Zero defects cannot be guaranteed by this audit or any finite test suite.
