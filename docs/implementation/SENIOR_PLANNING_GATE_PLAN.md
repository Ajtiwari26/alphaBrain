# AlphaBrain: researched planning before execution

Status: proposed implementation plan, not an implemented capability.
Repository inspected: `4f7b8f4`, 9 September 2026.
Scope: add an enforceable pre-implementation planning gate while preserving independent pre-merge review.
This proposal does not modify the canonical architecture document or authorize deployments.

## 1. Verified starting point

- `alpha_core/triage_cli.py:cmd_admit` extracts a specification through Eva, or accepts explicit manual fields.
- `cmd_approve` evaluates SafetyGate and approves worker intake; it does not require a researched planning attestation.
- `alpha_core/queue/triage_queue.py:lease_next_approved_task` checks task status and dependencies, but not planning approval.
- `alpha_core/state/task_engine.py:lease_next_task` is a separate control-plane execution route. Both routes must enforce the new rule.
- `alpha_worker/senior_review_engine.py` has structured AGY invocation and post-implementation verdict handling. Its current reviewer prompt restricts source inspection to supplied diff; this is insufficient for architecture review.
- Existing protocol, model router, task provenance, approval, and recovery mechanisms should be extended, not replaced.
- Tool availability and model availability must be detected. Do not assume names from pasted conversations are currently callable.

## 2. Intended workflow

```text
Eva/manual request -> deterministic admission checks -> pending task
    -> research snapshot -> Pro draft -> Opus challenge -> final plan agreement
    -> deterministic plan validation -> founder approval of exact execution packet
    -> lease -> isolated implementation -> independent gates
    -> Pro/Opus candidate review -> founder promotion policy -> promotion
```

The planning loop improves decisions; it does not make generated code deterministic or eliminate bugs. Model agreement is advisory evidence. Deterministic checks and runtime tests remain mandatory.

Research and planning run through a coordinator with read-only repository access and a constrained research broker. Do not enable unrestricted network or filesystem access in the coding worker to make research work.

## 3. Contracts and persistence

Add strict, versioned schemas, initially in `alpha_protocol/planning.py`:

| Contract | Required contents |
|---|---|
| ResearchSnapshot | task/project ID, repository identity, base SHA, request digest, policy version, retrieval time, sources, unresolved questions, graph snapshot digest |
| SourceEvidence | canonical URL or repository path/commit, publisher, version relevance, retrieval time, content digest, bounded excerpts, supported claim IDs |
| PlanBlueprint | immutable revision, input/research digests, base SHA, requirements, alternatives, chosen design, contracts, file scope, dependency DAG, gates, security decisions, rollback, budgets |
| PlanAssessment | reviewer principal, role, actual model, plan digest, APPROVE/REPAIR_REQUIRED/BLOCKED, findings tied to requirements/evidence |
| PlanningAttestation | purpose=`planning`, task/project/repository, base SHA, final blueprint digest, policy version, both assessments, issuer/key ID, issuance and expiry |

Keep planning attestation distinct from code-review/promotion attestation. Use purpose-separated signing and verification. Trusted coordinator signs only validated records; model text cannot mint authorization. An HMAC establishes integrity under its issuer's trust boundary, not independent model identity by itself.

Persist immutable blueprint revisions, assessments, source metadata, stage attempts, leases, and events in the existing durable store. Large source artifacts belong in content-addressed artifact storage. Keep secrets, full chats, and unnecessary client data out of prompts and logs.

Planning lifecycle, separate from existing execution status:

`required -> researching -> drafting -> reviewing -> ready`

Failure branches: `repair_required`, `blocked`, `stale`, `cancelled`. A task remains non-runnable until planning is ready AND execution approval is valid. Store stage lease owner, heartbeat, expiry, attempt count, next eligible time, and idempotency key. Do not hold database transactions during model or network calls.

## 4. Research and architecture requirements

For each task, first inspect existing implementations, lockfiles, tests, constraints, and graph context. Avoid automatic framework replacement.

Require live primary-source verification for changed APIs, dependency selection, provider limits, deployment behavior, security-sensitive platform assumptions, and other time-sensitive claims. Record the exact supported version; do not equate newest with appropriate.

Minimum blueprint sections:

1. User outcome, non-goals, assumptions, acceptance examples, unresolved questions.
2. Existing code to reuse and constraints to preserve.
3. At least two plausible approaches for consequential architecture choices, including maintaining the current approach.
4. Comparison of compatibility, operational cost, team maintenance, security, latency, reliability, licensing, and migration effort.
5. Selected design: interfaces, data ownership, state transitions, retries, concurrency, observability, failure recovery.
6. Small implementation packets with exact paths, dependency order, tests, and stop conditions.
7. Explicit research limitations. Unsupported API claims block affected work or require a bounded disposable feasibility experiment.

Research broker requirements: approved hosts, HTTPS, request/time/size limits, redirect and resolved-address validation, rejection of private/loopback/link-local metadata targets, no ambient credentials, and sanitized excerpts. Treat fetched pages, issue comments, task titles, and source comments as data, never instructions. Use GitHub MCP when needed. Graph data must match the inspected commit; stale graph results must trigger rebuild or disclosed bounded source inspection.

Do not let arbitrary researcher tool output become executable commands or override task permissions.

## 5. Planning consensus and token budget

- Pro: repository analysis and blueprint draft.
- Opus: focused challenge of architecture, risk, evidence, and acceptance coverage.
- Flash: bounded source indexing, formatting, and test-case enumeration; no final architectural authorization.
- Route through existing router using currently available model IDs and account policy. Never silently substitute a lower tier when a required reviewer is unavailable.

Both approvals must reference the SAME final blueprint digest. If Opus changes the design, Pro must assess that revised artifact; approving two different drafts is not consensus.

Suggested initial limits, configurable and recorded per plan: 2 revision cycles, 1 transport retry per stage, 300-second model-call timeout, 20 sources, 15-minute total planning budget. Stop at configured token/cost limits as well. Quota or repeated disagreements become durable blockers; no unlimited retries or emergency bypass.

Send compact source snippets and requirement IDs, not full chat histories. Cache research by repository/base, dependency versions, query and freshness policy. Cache review only for the exact approved artifact and policy. Every new runnable plan requires both assessments; cache reuse must not fabricate a new review.

Track planning tokens, wall time, revisions, implementation retries, escaped defects, and founder interruptions. Compare against baseline before claiming lower cost or better quality.

## 6. Enforcement and invalidation

Planning must be checked at approval, atomic lease acquisition, worker startup, result submission, and promotion. Put shared validation in one service used by both triage queue and control-plane TaskEngine. CLI-only enforcement is insufficient.

Execution approval binds the envelope digest AND planning attestation digest. Final envelope scope and executable gates must match the approved blueprint and pass SafetyGate again. No `--force`, direct retry route, healing task, or alternate API may waive missing planning evidence.

Changed requirements, repository/base, dependencies, permissions, gates, or policy invalidate approval. Worker discovery of an unsupported API or scope expansion emits `plan_change_required`; it must not silently redesign. Version the replacement plan and obtain approvals before resuming.

DAG children need plans bound to their actual execution base. Parent promotion may change that base. Revalidate impacted context and issue a new bound approval rather than retaining an obsolete SHA or automatically blessing rebased code.

Race protection: compare plan revision/digests and approval state within the same transaction that leases a task. Recheck immutable worker packet at dispatch. Test concurrent invalidation and competing coordinators.

Post-implementation reviewers receive the approved blueprint, requirement-to-test mapping, exact base/result diff, gate evidence, and bounded source context from the candidate snapshot. They must be able to inspect relevant source through a read-only broker; never execute candidate code with reviewer credentials. Review identities remain distinct from executor identities.

## 7. Bounded implementation packets

Each packet starts from a verified base in an isolated worktree. Before dispatch, enumerate exact allowed files and executable gate commands. Runtime changes below are PROPOSED.

| Packet | Work | Acceptance / stop condition |
|---|---|---|
| SP0 — contract audit | Map admission, approval, retry, lease, healing, submission and promotion routes; define threat model and fixtures | Every execution route accounted for; no behavior changes |
| SP1 — schemas/storage | Add typed artifacts, purpose-bound attestations, immutable revisions, coordinator leases and events | Reject malformed/duplicate fields, wrong task/base/purpose/digest, expired evidence; SQLite and PostgreSQL migration tests pass |
| SP2 — research broker | Source retrieval, graph freshness, artifact cache, capability detection | SSRF/redirect/prompt-injection boundaries, freshness expiry, no credentials in artifacts; missing sources reported honestly |
| SP3 — planning coordinator | Pro draft, Opus critique, bounded revision, final digest agreement, recovery | Different-plan approvals rejected; timeout/quota/restart/duplicate callbacks tested; no model calls inside DB transactions |
| SP4 — enforcement | Wire both execution paths, approval binding, stale invalidation, healing and DAG routes | Direct queue/API/CLI bypass attempts fail; races fail closed; old approvals cannot authorize changed plans |
| SP5 — execution/review | Inject compact immutable plan; bind result and code review to plan; read-only candidate context | Unplanned scope change blocks; independently failing gate blocks despite model approval |
| SP6 — controlled proof | One small external project through full lifecycle, then one low-risk self-development task | Durable lineage from request through plan, approval, implementation, review and promotion; no manual DB state repair |

Test additions belong under `testscript/`. Never add xfails to hide enforcement regressions. Full-suite validation must use isolated state and test credentials, not live Keychain secrets. Record skipped tests and exact reasons. Preserve current sandbox controls and immutable `alpha_meet/`.

For each code packet: focused tests, full pytest, Ruff lint/format, Mypy, committed-range diff/scope review, independent review against exact candidate. No push, deployment, migration of a live database, or merge merely because a model says APPROVE.

## 8. Rollout and existing tasks

Start in shadow mode: collect plans for selected non-running tasks while comparing results; shadow artifacts authorize nothing. Enable enforcement only after SP4 adversarial tests pass.

During cutover, pause new leases briefly and inventory existing tasks. Mark unleased tasks as planning-required. Let explicitly grandfathered active attempts finish under their original immutable policy, or cancel through audited transition. Do not silently downgrade enforcement on rollback.

Rollback stops new planning-dependent dispatch, preserves records, and restores compatible coordinator code. No record deletion, synthetic review, or direct SQL edits to make progress counters green. Old deleted task evidence remains a separate recovery issue requiring backups; this feature cannot reconstruct it.

## 9. Supervisor handoff prompt

> Implement SP0 first, then execute SP1–SP6 sequentially after each packet's verified acceptance. Read this plan and canonical architecture. Report conflicts before resolving them. For each packet, provide exact base, allowed paths, interface changes, threat cases, test commands and failure handling before worker dispatch. Reuse existing router, approval and evidence infrastructure. Models cannot expand permissions, mint their own approvals, skip planning, change founder-approved scope, or substitute unsupported evidence. Research and reviewers use constrained read-only access; coding workers retain sandbox restrictions. Do not confuse a planning attestation with implementation review. Stop at durable blockers with a specific repair or missing-input request. No live deployment or destructive queue mutation is authorized by this prompt.

## 10. Proposed operator UX (not current commands)

```bash
# Proposed: run/recover planning for one pending task.
.venv/bin/python -m alpha_core.triage_cli senior-plan <task-id>
# Proposed: inspect decisions, sources, unresolved findings and exact digest.
.venv/bin/python -m alpha_core.triage_cli plan-show <task-id>
# Proposed: approve the exact combined planning/execution packet.
.venv/bin/python -m alpha_core.triage_cli approve <task-id> --plan-digest <digest>
```

Definition of done: real planning and execution gates enforce the same immutable artifacts through both runtime paths; restart and adversarial tests pass; external and self-development proofs complete; evidence shows costs and limitations. Model consensus or a new architecture document alone is not completion.
