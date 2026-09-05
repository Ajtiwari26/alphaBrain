# Astra exit-gap repair packets

Prepared 2026-09-05 from `a13a24d9e98ede77f624a9db6540baf8f7fea263` plus existing dirty reviewer flag. Proposed implementation; no runtime repairs made by this document.

## Decision and execution contract

A1/A3 remain rejected. Green tests missed reproducible false approval. Plain SHA-256 is not an authenticated signature. Worktree plus timeout is not OS containment. Trusted runtime must enforce these boundaries.

Capture base SHA, dirty paths, active task ownership, and graph freshness. Preserve unrelated changes. Freeze one packet's file scope after dependency inspection. Use authorized AlphaBrain dispatch workflow; this plan does not grant founder execution/promotion approval or bootstrap permission. If broken pipeline blocks repair, report exact blocker; never fabricate evidence or alter task status directly.

Reuse original TaskEngine/protocol/auth infrastructure instead of inventing a third lifecycle. Tests belong under `testscript/`. Prove defects before repair and inspect assertions after repair. Record focused/full pytest, Ruff check/format, Mypy, committed and uncommitted whitespace/scope checks. Required skipped infrastructure proofs remain unverified. Evidence goes under `testscript/evidence/astra-tightening/<packet>/<attempt>/` with base/result SHA, scope, command exits, negative probes, and remaining limitations. No credentials in logs.

## T1 — Reviewer protocol and honest coverage

Scope: `alpha_worker/senior_review_engine.py`, `testscript/test_astra_a1_a3_exit_gaps.py`, dedicated reviewer tests if explicitly included in packet.

Reasoning may precede one exact JSON verdict on last nonempty line. Parse the complete line; never extract a regex substring. Reject duplicate keys, extra keys, wrong types/enums, quoted/fenced/embedded verdicts, trailing text, and ambiguous multiple verdict records. Use role-specific enums. Missing/nonexecutable binary, timeout, nonzero exit, malformed output, and unavailable actual diff must not mint approval.

Do not silently truncate a large diff then claim complete review. Require bounded complete coverage or an explicit review strategy with coverage evidence.

Regression matrix:
- Invalid Pro embedded approval + valid Opus approval => Pro and aggregate reject.
- Valid Pro approval + invalid Opus embedded approval => Opus and aggregate reject.
- Both contain quoted approval JSON followed by `Final decision: REJECT` => reject (currently approves).
- Duplicate JSON verdicts/keys, wrong enum, fenced output, trailing text, incomplete output => reject.
- Valid reasoning plus terminal JSON => valid parsing only, not promotion authority.
- Valid approval text with nonzero exit, missing binary, or timeout => no persisted approval.

Current aggregate-only parser test passes because Opus receives Pro's `APPROVE` enum. Replace that blind spot with independent stage assertions.

Reviewer must not modify source, tests, config, approvals, or credentials. Reconcile existing dirty permission flag with owner. Removing a CLI bypass alone does not prove containment; until A5 provides enforced isolation, accurately label review as supervised. Never silently equate CLI prompt permissions with a security sandbox.

## T2 — Authenticated ownership and atomic fencing

Scope: triage API, queue lease/result operations, existing security contracts, dedicated API/concurrency tests.

Bind lease owner to authenticated subject. Payload worker ID is not authority. Founder/admin delegation must be explicit, project-scoped, and audited. Lease selection and submission must enforce project access.

Persist owner, random lease ID, attempt ID, per-task monotonic epoch, and expiry transactionally. `int(time.time())` is not a unique increasing epoch. Complete/fail/retry in a transaction with update predicate matching task state, owner, lease, attempt, epoch, and validity. Pre-read followed by unqualified update is insufficient. Local dispatcher must follow the same contract as HTTP.

Tests: worker A cannot complete B's task even with copied payload metadata; cross-project denied; expired lease denied; stale result after reassignment denied; concurrent completion produces one outcome; exact replay follows explicit idempotency rules; failure path has same fencing; epoch increases within one second; restart preserves lease ownership. Force race between validation and reassignment, not just sequential mocks.

## T3 — Authenticated review bound to actual evidence

Scope: protocol models, queue review persistence, review engine, trusted signing/auth service, attestation tests; freeze exact allowlist after graph inspection.

Versioned canonical attestation requires project/task/attempt, packet digest, exact base/result SHAs, final diff digest, actual gate evidence digest, authenticated reviewer and executor principals, verdict, issuance/expiry, key ID, schema version. No empty manifest defaults or synthetic identity.

Hash actual typed `evidence` emitted by dispatcher, not absent `acceptance_manifest`. Validate required gates and task/attempt/commit bindings. Reject duplicate/unknown evidence identities and executor-supplied independent review.

Trusted service signs only after authenticating independent reviewer. Reuse existing signing infrastructure with domain separation or appropriate asymmetric keys. Executor never receives signing authority. Plain hash is only an integrity digest. Promotion verifies signature, trusted key, expiry, identity separation, and all bindings. Preserve immutable review history instead of overwriting prior approval.

Tests: missing/forged signature; modified task/attempt/SHA/evidence/verdict; wrong/revoked key; expired review; same executor/reviewer; missing gate evidence; changed code after review; valid independently authenticated attestation. Signature generated but never verified is rejection.

## T4 — Race-safe promotion of reviewed commit

Scope: merge CLI, shared worktree/promotion helpers, queue/protocol integration, real disposable Git tests.

Require equality of actual result SHA, signed review SHA, requested promotion SHA, packet base, and final diff/evidence. No fallback between inconsistent fields. Validate complete object IDs, commit type, ancestry, approved destination, source cleanliness, and actual scope.

Acquire cross-process repository promotion lock. Enforce expected target base and merge exact immutable result SHA, never branch name. Protect target ref with compare-and-swap or equivalent against writers outside cooperative lock. Verify final HEAD and persist outcome. Crash after merge before acknowledgement must replay idempotently with all bindings rechecked. Never force-remove worktree with unverified changes.

Tests: branch moves after validation; main moves concurrently; concurrent same/different task promotion; result/review SHA disagreement; dirty/colliding user files; crash before merge and after merge before acknowledgement; replay; invalid signature; missing evidence. Every rejection must leave repo/task unchanged unless explicitly reporting already-completed identical promotion.

## T5 — Frozen packets, final scope, gates, DAG, retries

Split into bounded subpackets after graph review; scope spans producer, dispatcher, queue, shared protocol/worktree code and tests.

- Resolve full commit SHA before approval. Reject unresolved `main`, tags, `HEAD~1`, and missing bases, not only literal `HEAD`. Require full canonical envelope digest. Legacy partial hashes require explicit migration before admission.
- Validate typed required gates before leasing. Separate automated gates from deferred independent review. Reject ambiguous empty plans, unknown/duplicate definitions, missing commands, and mismatched evidence according to explicit task contract.
- Inspect exact final base-to-result diff after execution and gates: committed changes, renames, deletions, additions, symlinks, submodules, forbidden paths. Enforce actual file/line budgets. Recheck after anything that may mutate source. Evidence must bind final tree, not earlier working-tree status.
- Children consume explicit verified/promoted parent artifact commit. Parent execution `completed` alone cannot unblock dependent build.
- Maintain cumulative repair budget across attempts/manual retries. Exhaustion blocks with actionable evidence; resetting per-attempt counters must not erase lifetime limits.

Tests: symbolic ref and partial-hash rejection; command change invalidates approval; committed out-of-scope file; gate creates file; directory allowlist exceeds actual budget; parent awaits/rejects review; child consumes wrong SHA; repeated retries cannot reset cumulative budget.

## T6 — Integrated proof and truthful context

Run one harmless task through real isolated admission, authenticated lease, AGY execution, required gates, independent authenticated review, explicit promotion authorization, and exact commit promotion. Use disposable repo/state. No manual review simulation or direct DB transition. Record actual model/tool availability.

Inject review failure, stale submission race, and promotion restart. Prove blocked/retry paths plus valid recovery. Unit mocks do not replace workflow evidence. Staging/deployment remain separately authorized work.

Refresh graph, compact context, current report, and TODO evidence. Request authorized Opus owner reconcile canonical architecture's outdated phase and containment claims. Keep audit history. Status vocabulary: implemented, local verified, staging verified, blocked; no blanket autonomy percentage.

## Supervisor handoff prompt

Read compact context, this packet, current git status, and fresh graph queries. Start T1 only. Preserve existing dirty reviewer change until ownership resolved. Follow authorized AlphaBrain dispatch workflow; no bypass authority is granted here. Return bounded patch with independent failing-before/passing-after parser evidence. Do not accept old test totals as proof. Proceed T2 after T1 acceptance. Keep prompts limited to current packet, affected graph nodes/source/tests, and latest evidence. Report blockers instead of mutating task state or weakening gates.
