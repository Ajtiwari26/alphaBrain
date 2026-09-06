# AlphaBrain engineering remediation and delivery handoff

Date: 2026-09-06.
Reviewed repository: `/Users/ajaytiwari/Desktop/Projects/alphaBrain`.
Verified HEAD when preparing this document: `388b77aa2cf2959710fa5d94488f6d13f3c12e13`.
Purpose: consolidated review, corrected implementation plan, team operating design, acceptance criteria, and supervisor prompts.
Status: **design accepted with the corrections below; implementation and overall autonomy remain unaccepted**.

This document is a proposed engineering handoff, not founder task approval, promotion approval, deployment permission, or permission to bypass the current execution policy. Historical evidence must be rechecked if HEAD changes.

## 1. Verdict on submitted plan

The submitted R0–R6/F1–F7 plan identifies the right problems and a useful order. Proceed with baseline analysis and preparation of bounded packets using this corrected version. Do not interpret architectural agreement as blanket approval of future task execution or promotion.

Required corrections:

1. **Do not fabricate canonical hashes.** `"a" * 40` is suitable only for a schema-only test that intentionally does not resolve Git objects. Git integration tests need actual temporary repository commits. Packet hashes must be computed from the exact canonical envelope; `"b" * 64` is not a valid substitute for an integrity test.
2. **Do not require the broken pipeline to certify itself.** Prepare work using its authorized flow where viable. If known review/promotion defects prevent trustworthy execution, stop automatic promotion and prepare a separate isolated bootstrap-repair proposal with exact scope and independent verification. Explicit bootstrap authority is required; do not fabricate approvals or manipulate database states.
3. **Preserve useful unit tests.** R6 needs a separate opt-in live proof. Retain existing useful mocked tests under accurate names, repair misleading assertions, and remove only demonstrably redundant/invalid tests with justification. Mocking is appropriate for unit tests, not evidence that real AGY and promotion succeeded.
4. **R2 must bind more than task ID and evidence.** Require project, attempt, immutable packet, base/result/diff, executor/reviewer identity, evidence, expiry, key ID, and schema version. Verify every field against trusted current records.
5. **R3 must cover lease expiry and transaction semantics.** Four strings alone do not provide isolation or recovery. Require identity binding, monotonic epochs, expiry, atomic mutation, and explicit replay behavior.
6. **R4 must protect destination state.** A cooperative file lock is insufficient against unrelated Git writers. Validate and conditionally update the expected target revision, record durable promotion state, and prove crash recovery.
7. **R5 needs trusted verification profiles, not an executable blacklist.** Banning `echo` still permits `python -c 'pass'` or an empty test script. Bind approved commands, test selection, runner configuration, and meaningful assertions to the task contract.
8. **Reuse authoritative lifecycle contracts.** Do not declare the newer SQLite triage queue the sole production authority without consolidating the stronger original TaskEngine contracts and deciding shared control-plane storage ownership.
9. **Read-only review must be enforced.** Tool names and prompts do not prevent filesystem writes or credential access. Reviewers need exact result-tree access in a constrained environment, without executor/promotion secrets.
10. **Avoid inventing new status names casually.** Map authorization-required states onto existing protocol states where possible. Any new state needs a versioned migration and transition tests.

## 2. Evidence and current capability boundary

Independent review at this snapshot:

| Check | Observed result |
|---|---|
| Full pytest | 180 failed, 490 passed, 13 errors, 11 skipped |
| T6 test file alone | 6 passed |
| Ruff check | Passed |
| Mypy | Passed; 74 source files |
| Ruff format | 20 files require formatting |
| Code Review Graph | Current at `388b77aa2cf2`; 2,015 nodes, 24,995 edges, 206 files |

The submitted report's 29-node graph figure does not match full graph status. Do not confuse incremental update counts with total graph coverage.

The first independently isolated suite failure is a TaskEnvelope fixture missing required `base_commit`. Other failures need classification; this observation does not prove all failures are fixture debt.

Three bounded negative probes used actual parsing/promotion code with mocked Git, without changing the source repository:
- Approval JSON followed by `Final decision: REJECT` parsed as `APPROVE`.
- Missing attestation still reached successful merge return.
- Valid signature for another task, with different current evidence, still reached successful merge return.

Real improvements exist: exact-result-SHA merge, cross-process lock, HMAC implementation, stronger API ownership checks, canonical queue admission, cumulative retry fields, and final diff inspection. They are incomplete safeguards, not proof of the entire delivery lifecycle.

T6 currently uses a DummyBridge, `echo passed` labeled as unit testing, direct SQLite review updates, and mocked Git merge. It exercises selected integration paths but does not establish actual independent AGY review or live promotion.

TODO contains 176 checked and 229 unchecked items at this snapshot. This is documentation state, not an engineering completion percentage. Original P9 means specification intelligence; newer P9 means self-development. Reconcile phase naming before reporting progress.

## 3. Findings to close

| ID | Finding | Current source |
|---|---|---|
| G1 | Reviewer scans backwards for any parseable verdict; trailing rejection can be ignored | `alpha_worker/senior_review_engine.py::parse_verdict_line` |
| G2 | Attestation verification is conditional on its presence | `alpha_core/triage_cli.py::cmd_merge` |
| G3 | Wrong-task/evidence attestation accepted; validity and authenticated reviewer separation incomplete | `alpha_protocol/task.py::ReviewAttestation`, merge verifier |
| G4 | Public hardcoded signing fallback; review hashes `gate_result` while dispatcher emits `evidence` | senior review engine and merge CLI |
| G5 | Internal completion/failure fencing optional; dispatcher completion omits tokens | queue and dispatcher |
| G6 | Parent approval boolean substitutes for durable promoted artifact | queue dependency query |
| G7 | Empty acceptance plan permitted; command label does not prove meaningful testing | dispatcher gate validation |
| G8 | Senior repair changes packet digest and directly approves it without checking lifetime repair budget | `queue_task_for_senior_repair` |
| G9 | Pro opinion precedes Opus review; Opus is denied source inspection | senior review prompts |
| G10 | SDLC demo auto-approves spec/preview and sets deployed without provider evidence | `alpha_core/workflow/sdlc_workflow.py` |
| G11 | Intake planning is coupled to AlphaBrain paths and lacks enforced research/design artifacts | Eva extractor and task proposer |
| G12 | Full-suite regressions, format failures, stale status documents, and overstated proof | tests and status reports |

## 4. Target system design

Retain existing Python/FastAPI/Pydantic foundation. First consolidate task authority; do not start a framework rewrite to repair security defects.

Use one authoritative contract for admission, lease, result, review, repair, and promotion. The existing TaskEngine should be inspected for reusable typed gates, identity, approvals, and promotion semantics. The triage API/CLI should call that authority or share the same validated transitions rather than implement weaker parallel rules.

Shared control-plane records belong in the chosen durable service database, with an explicit migration from any local-only authoritative queue. Local SQLite can serve isolated development and encrypted worker spool/cache. Avoid assuming multiple hosts share a local queue safely.

Conceptual lifecycle (map onto existing enums before implementation):

```text
Requirements draft -> research/design -> approved specification
 -> immutable task admission -> authorized execution -> leased attempt
 -> implementation -> automated verification -> independent review
 -> authorized promotion -> durable promoted artifact -> dependent tasks
 -> preview -> founder feedback -> approved refinement or deployment
```

Failure transitions must be explicit:
- Transport outage: bounded retry with preserved idempotency keys.
- Invalid evidence or ownership: reject with immutable reason.
- Code defect: bounded repair attempt preserving original approved scope.
- Scope, budget, dependency, or acceptance change: new packet/version requiring authorization.
- Repeated identical failure: escalate with reproduction and remaining options.
- Crash after external effect: reconcile observed effect before retrying.

Model output is a proposal. Deterministic code owns authorization, counters, state transitions, result acceptance, and promotion.

## 5. Senior, mid-level, junior, QA, and controller roles

| Role | Responsibility | Deliverable | Authority boundary |
|---|---|---|---|
| Founder/product owner | Objectives, budget, scope, business acceptance | Approved spec and required decisions | Grants explicit scoped authority |
| Senior architect | Tradeoffs, threat model, architecture, disputed findings | Design decisions and acceptance criteria | Cannot replace founder permission |
| Mid-level planner | Decompose design and define interfaces/dependencies | Immutable bounded packets, integration plan | Cannot silently broaden scope |
| Implementer/junior | Execute one bounded task | Exact commit and local test evidence | No review-signing or promotion credentials |
| Independent QA/reviewer | Challenge behavior, tests, security and completeness | Findings plus attestation request for exact artifacts | Cannot modify reviewed result |
| Senior adjudicator | Resolve conflicting reviews with reproduction | Documented disposition and revised criteria if authorized | Cannot vote away failing hard gates |
| AlphaBrain controller | Validate policy, persist transitions and budgets | Durable audit and approved actions | Deterministic enforcement |

Roles are not equivalent to model brands. Assign available verified models by task difficulty, cost, latency, and demonstrated quality. Keep existing mandatory senior-review policy until its owner explicitly approves changes.

Suggested routing: senior-class model for architecture/security/disputes; coding-class model for difficult implementation/planning; faster model for mechanical tasks and evidence formatting. Use actual installed model IDs and recorded provider responses. No model upgrade claim is established by this document.

Independent review procedure:
1. Freeze exact result commit and evidence bundle.
2. Reviewer examines requirements, acceptance criteria, full relevant result source and tests before seeing implementer's or another reviewer's verdict.
3. Record first-pass findings independently.
4. Compare findings; senior adjudicates material disagreement with reproduction.
5. Trusted controller verifies hard gates and authenticates review issuance.

Two models seeing the same persuasive summary are not independent verification. Reviewers need sufficient unchanged context as well as diff. Running checks requires a constrained environment; read-only source mounts, restricted credentials/network, and disposable outputs should enforce scope.

## 6. Repair-loop design and optimization

Use structured findings: ID, severity, requirement, exact artifact SHA, location, reproduction, expected behavior, proposed repair, and regression criterion. Do not repeatedly append full debate transcripts to task instructions.

Track per-task cumulative attempts, elapsed time, model/tool cost, review cycles, and repeated failure fingerprint. Counters survive manual retries, restarts, and senior rejection. Budget exhaustion blocks with actionable report.

Allow automatic repair only within already-approved scope and budget under explicit policy. Changed requirements, allowed paths, acceptance conditions, dependencies, or execution budget create a new approval-bound packet. Preserve parent packet and audit lineage.

Classify failures before escalation: transient provider outage, invalid protocol, environment defect, implementation defect, missing requirement, or authority violation. Each needs a distinct retry/escalation policy.

Cost metrics: cost per accepted task, first-pass acceptance, escaped defects, repair rounds, review reversals, queue time, and total delivery latency. Benchmark routing changes on the same representative task set. Token savings without preserved quality do not count as optimization.

Use compact context + current packet + graph neighborhood + relevant source/tests + latest evidence. Record graph HEAD and dirty source fingerprint; stale graph cannot certify current code. Cache immutable design artifacts by digest; invalidate review/evidence whenever inputs change.

## 7. R0 — Baseline and test recovery

Capture exact current revision, dirty ownership, dependency lock, and test environment. Do not reset or clean unrelated changes.

Classify each failure cluster: tightened-contract fixtures, runtime regression, order/isolation issue, or infrastructure absence. Split repairs into bounded packets. Format-only changes should be independently identifiable.

Use real temporary Git commits for object/ancestry tests and canonical digest helpers for envelope tests. Placeholder hashes are only for schema-only validation. Preserve security assertions and required migrations/PG tests.

Acceptance: all required tests pass; skipped requirements explicitly unresolved; lint/format/type checks pass. Log failing-before/passing-after evidence. Full-suite success is not itself live product proof.

## 8. R1 — Strict reviewer protocol

Parse the complete last nonempty verdict line with strict keys, types, and role-specific enums. Reject duplicate keys, extra keys, invalid enum, embedded/fenced verdicts, conflicting records, and trailing non-whitespace text. Define legitimate reasoning separately from verdict syntax.

Missing executable, nonzero exit, timeout, malformed output, or missing actual review input must fail closed with structured invocation evidence. Do not approve partial/truncated review coverage.

Tests must isolate Pro and Opus stages: invalid Pro with valid Opus; valid Pro with invalid Opus; both invalid; valid pair. Reproduce approval JSON followed by rejection. Aggregate-only assertions must not mask a falsely approved stage.

Acceptance: every negative case rejects at the responsible stage; valid terminal verdict parses; parsing alone cannot create promotion authority.

## 9. R2 — Mandatory authenticated review

Make attestation mandatory. Remove default signing key; absent configuration blocks before model work or promotion. Separate signing authority from executor environment and restrict key access. Define key rotation/revocation and validity checks.

Required versioned canonical fields: project/task/attempt, immutable packet digest, base/result SHA, final diff/tree digest, actual typed evidence digest, reviewer/executor principals, verdict, issued/expiry times, key ID and schema version.

Verify all bindings against trusted current records. Hash real dispatcher evidence; missing evidence must not become an empty signed dictionary. Reject contradictory verdict/approved combinations. Preserve immutable attestation history rather than overwrite authority.

Tests: missing signature, wrong key, expired review, wrong task/project/attempt, modified evidence, modified commit, same executor/reviewer, missing required gates, invalid schema version, revoked identity, and valid independent attestation.

Acceptance: the previously accepted missing-attestation and wrong-task/evidence probes fail before any Git mutation.

## 10. R3 — Mandatory fenced mutations

Every worker-owned completion/failure/renewal/release must require authenticated owner, attempt ID, lease ID, monotonic fencing epoch, and valid lease. Remove optional fallback signatures. Local worker and HTTP routes share one contract.

Validate and mutate atomically using full ownership/state predicates. Select only project-eligible work instead of repeatedly leasing and releasing an inaccessible oldest task. Define founder/admin delegation explicitly.

Tests: copied metadata from another worker, cross-project attempt, stale lease after reassignment, expired lease, concurrent completion, valid exact replay, changed replay payload, failure-path fencing, restart, and monotonic epoch within same clock tick.

Acceptance: no mutation path can bypass fencing by omitting one field. Exactly one valid completion/audit outcome under forced race.

## 11. R4 — Promotion and dependency artifacts

Under repository coordination, reload task/review state, authenticate attestation, validate expected destination base, object type, ancestry, exact scope and source cleanliness. Merge exact reviewed SHA. Protect destination revision against non-cooperating writers through compare-and-swap or equivalent mechanism.

Persist promotion intent/outcome. Crash after merge before acknowledgement must reconcile exact result and finish once. Cleanup is recoverable and must not force-remove unverified work.

Dependencies consume explicit promoted/verified artifact SHA according to policy, not only `approved=true`. Persist source artifact relation and verify child's base/input includes it.

Tests: concurrent promotions; target advances; branch changes; mismatched signed SHA; dirty/colliding files; crash before/after merge; replay; parent approved but unpromoted; rejected parent; wrong dependency artifact.

Acceptance: exact commit promotion and durable replay proven with real temporary Git; no unrelated file/ref changed on rejection.

## 12. R5 — Meaningful gates, scope and repair budget

Validate frozen complete packet and trusted verification profile before execution. Reject empty/ambiguous coding plans, missing required commands, duplicate/unknown gate types, and executor-supplied independent review.

Use approved test/build/security profiles appropriate to project. Check test collection and actual behavioral assertions; an executable named pytest or a declared unit_test label is insufficient. Changes to verification configuration/tests require review and potentially independent retained regression coverage.

Bind evidence to final result tree. Inspect committed and uncommitted changes, deletions, renames, symlinks, submodules, residue and actual file/line budgets. Revalidate after any gate/hook that can change source. Never accept stale evidence after code mutation.

Implement cumulative repair governance from section 6, including senior rejection path. Use existing authorization-state contracts rather than invent unimplemented states in prompts.

Tests: trivial/empty test gate; wrong evidence commit; missing required gate; committed forbidden file; gate-generated source change; directory budget overrun; packet mutation; repeated senior/manual retry cannot reset lifetime budget.

## 13. R6 — Real integrated proof

Keep fast unit tests and mark their mocks accurately. Create a separate live proof harness using disposable repository and isolated state, with explicit authorization for required model calls and promotion.

Required sequence: real admission and safety evaluation; approved immutable packet; identity-bound lease; real AGY code change; meaningful tests; actual independent review; authenticated attestation; authorized exact commit promotion; real Git verification and durable audit.

No direct SQL approvals or state manipulation. No DummyBridge, fake test command, fabricated reviewer, or mocked merge may stand in for the live proof. Test fixtures can exist outside this proof without being misrepresented.

Inject review rejection, stale submission, outage/restart, and promotion contention. Verify both fail-closed paths and successful recovery. Unavailable provider/infrastructure means blocked/partial, not complete.

Acceptance: repository contents, task state, evidence and promotion audit agree on exact task/attempt/SHAs. Independent reviewer can reproduce the claim. No production deployment implied.

## 14. Future delivery phases

Begin after accepted R6, with architecture artifacts prepared earlier where useful.

| Phase | Required capability | Exit proof |
|---|---|---|
| F1 Research/specification | Source ledger, alternatives, build-vs-integrate, constraints, ADRs, threat model, acceptance mapping | Approved traceable spec; selected stack justified by project needs |
| F2 External project | Project-specific DAG, implementation, browser/API QA, preview and refinement | One real external project satisfies every advertised requirement |
| F3 Operations | Durable workflow, worker outage/restart, provider failure, budget controls, backups | Recovery and restore drills without duplicate effects |
| F4 Portal | Role-scoped status, evidence, blockers, approvals, previews | Founder/client journeys and tenant isolation verified |
| F5 Eva meetings | Duplex audio, consent, traceable transcript/spec revisions | Real participant/RTC/provider proof, not backend-only success |
| F6 AgentLine | Verified calls and documented founder directions | Call facts tied to evidence; directions create reviewable change requests |
| F7 Deployment/pilots | Confirmed previews, approved production, rollback, monitoring/privacy | Internal then friendly-client pilot with recorded defects and retests |

F1 must not map the word “app” directly to Flutter or any preset. Compare candidate stacks against offline/device needs, team skills, performance, accessibility, portability, operations, licensing, ecosystem maturity and lifecycle cost. Use current primary sources for changing technology facts.

Quarantine demo auto-approval/deployed paths from live execution. Replace them through the authoritative lifecycle; do not wire a demo runner into production merely because it exposes a run method.

Inspect project metadata and resolved Git state for Eva planning. Remove hardcoded AlphaBrain paths from generic project intake. Preserve current immutable `alpha_meet/` boundary until separately authorized coordination changes it.

Temporal is an existing roadmap option for durable orchestration, not a prerequisite for these repairs. Decide adoption with an architecture record; workflow durability does not eliminate idempotency or authorization obligations.

## 15. Verification commands and evidence format

These are baseline checks, not an authorization to execute arbitrary generated commands. Run from the intended isolated checkout with its locked environment.

```sh
# Capture exact repository state before work.
git status --short
git rev-parse HEAD
# Check graph freshness before selecting relevant nodes.
code-review-graph status --repo .
# Verify Python style and types without silently fixing code.
.venv/bin/ruff check --no-cache .
.venv/bin/ruff format --check .
.venv/bin/mypy alpha_core alpha_protocol alpha_worker
# Run complete test suite and report skips explicitly.
.venv/bin/pytest -q -p no:cacheprovider
# Check current uncommitted whitespace; also run a separate exact-base..result check.
git diff --check
```

Use real recorded SHAs for committed-range review, not `HEAD` alone after a commit. Preserve exact process exit codes when logging commands; a successful `tail` must not mask failed pytest.

```text
PACKET:
BASE_SHA:
RESULT_SHA:
DIRTY_PATH_OWNERSHIP:
CHANGED_FILES:
DEFECT_REPRODUCTION:
FOCUSED_TEST_RESULTS:
FULL_SUITE_RESULTS:
SKIPS_AND_REASONS:
RUFF:
FORMAT:
MYPY:
SCOPE_AND_DIFF_CHECK:
INDEPENDENT_REVIEW_AND_BOUND_ARTIFACTS:
LIVE_PROOF_OR_MOCK_BOUNDARY:
REMOTE_MUTATIONS:
REMAINING_RISKS:
DECISION: ACCEPT / REPAIR_REQUIRED / BLOCKED
```

Store sanitized evidence under `testscript/evidence/astra-remediation/<packet>/<attempt>/`. No secret values, bearer tokens, or raw credential environment in evidence.

## 16. Copy-paste Antigravity supervisor prompt

```text
Read docs/implementation/ASTRA_COMPLETE_ENGINEERING_HANDOFF.md first.
Use current git status, latest diff, and focused Code Review Graph queries.
Do not reload old chat history for routine work.

The R0–R6 plan is accepted as a corrected design, not as completed implementation
or blanket authorization. Begin R0 failure classification and prepare one bounded
repair packet. Preserve concurrent work. Use authorized AlphaBrain dispatch;
if known pipeline defects prevent trustworthy operation, report that blocker and
prepare an isolated bootstrap proposal rather than bypassing approvals.

Use real Git commits for integration fixtures and canonical computed packet hashes.
Do not weaken schemas, remove security assertions, or hide failed/required skipped tests.
Keep useful unit tests; distinguish them from a separate real R6 proof.

R1 fixes terminal parsing. R2 makes authenticated attestation mandatory and fully
bound. R3 requires atomic fencing everywhere. R4 proves exact artifact promotion
and dependency lineage. R5 verifies meaningful gates, final scope and lifetime
repair budgets. R6 exercises actual AGY, tests, independent review and Git promotion
without direct database transitions or mocked external effects.

Assign roles explicitly: architect, planner, executor, independent reviewer,
adjudicator, deterministic controller. Reviewers record independent first-pass
findings before debate. Hard gates cannot be voted away. Changed scope requires
new authorization; same-scope repairs consume bounded lifetime budget.

Return exact evidence format from section 15 after each packet. Refresh compact
context and graph after accepted changes, recording current SHA and dirty state.
Do not call the roadmap complete until integrated proof and acceptance criteria pass.
No push, deployment, migration, credential change or production worker interruption
is implied by this prompt.
```

## 17. References and maintenance

- Prior findings: `ASTRA_ENGINEERING_AUDIT_2026-09-05.md`.
- Earlier detailed repair criteria: `ASTRA_EXIT_GAP_REPAIR_PACKETS_2026-09-05.md`.
- Research/architecture expansion: `ASTRA_RESEARCH_AND_AUTONOMY_EXECUTION_PLAN.md`.
- Compact status: `ALPHABRAIN_COMPACT_CONTEXT.md` (September 5 snapshot is historical until reconciled).
- Canonical architecture: `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`, owned by designated senior; request reconciliation rather than silently overwrite it.
- [SLSA artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts): provenance verification must match artifact identity and expected trusted provenance.
- [Temporal architecture](https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md): durable execution still requires deterministic workflow behavior and appropriate side-effect/idempotency handling.

Future status updates must name observed capabilities, exact commit/evidence, and limitations. Keep implemented, local verified, staging verified, production verified, blocked, and untested distinct. No plan or model verdict establishes bug-free software.
