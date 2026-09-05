# AlphaBrain Current Report

## Current status — 2026-09-05

Snapshot: `main` at `a13a24d9e98ede77f624a9db6540baf8f7fea263` plus user-owned dirty reviewer permission flag. A1/A3 are **partially repaired, not accepted**. Reproduced false approval from embedded JSON followed by rejection. Review checksum is unsigned/unverified; promotion has a branch race; lease identity is not bound to principal and result mutation is not atomically fenced.

Independent focused checks: 12 tests passed; lint passed on four boundary files; formatting failed on four. Full-repository Ruff check also passed during documentation update. Commit's full-suite claim not independently rerun here. No new live/staging claim.

Current handoff: [compact context](implementation/ALPHABRAIN_COMPACT_CONTEXT.md) and [T1–T6 repair packets](implementation/ASTRA_EXIT_GAP_REPAIR_PACKETS_2026-09-05.md). Graph status now reports `main`, `a13a24d9e98e`, updated `2026-09-05T19:38:05`, 1,958 nodes and 24,288 edges. Graph HEAD does not identify dirty edits. Existing canonical architecture requires owner reconciliation.

Everything below is archived August 31 evidence; do not use it as current completion status.

---

**Audit date:** 2026-08-31

**Audited revision:** `f18557c` plus local approved-spec planning changes

**Remote mutation:** None during this work

**Decision:** Local stabilization, atomic graph admission, and approved-spec task drafting accepted.
Changes remain local and are not deployed.

## Verified local evidence

| Area | Status | Evidence |
|---|---|---|
| Full pytest | Passing | `526 passed, 1 skipped in 40.72s` with Docker active |
| PostgreSQL gates | Passing | 10/10 migration, checkpoint, and watchdog-concurrency tests |
| Ruff lint | Passing | `ruff check .` reports zero findings |
| Ruff formatting | Passing | 167 active files formatted |
| Mypy | Passing | Zero errors across 64 files in core, protocol, worker, and meet packages |
| JavaScript syntax | Passing | `node --check alpha_meet/frontend/js/meet.js` |
| Patch integrity | Passing | `git diff --check` clean |
| Repository root | Organized | One-off repair scripts archived under `testscript/archive/legacy_repairs/`; historical logs under `testscript/evidence/legacy/` |
| User-owned local state | Preserved | `alpha_meet/frontend/.gitignore` remains untracked and untouched |

## Repairs completed

- Restored adapter checkpoint callback compatibility across base, unsupported, and Claude adapters.
- Removed unsafe duplicated Eva configuration logic and added concrete background-task/translator types.
- Added internal non-admin LiveKit `translator` role.
- Configured Gemini Live Translate with input/output transcription and official translation configuration.
- Replaced translation scripts that swallowed provider errors with deterministic endpoint and configuration tests.
- Protected `/api/meet/translate-text`: founder token or signed meeting invite now required.
- Enforced validated BCP-47-style target language input and honored requested target language.
- Removed translated-text `innerHTML` injection; provider output now renders through DOM text nodes.
- Updated stale meeting mocks and retained current LiveKit `RoomEvent.TranscriptionReceived` contract.
- Repaired repository-wide Ruff/format defects and checkpoint harness duplicate configuration.
- Added founder/admin-only `POST /api/projects/{project_id}/task-graph` admission for 1–50 frozen
  task envelopes.
- Added atomic prevalidation for cycles, duplicate task/dependency IDs, missing or nonterminal
  external dependencies, project/repository binding, and explicit per-task approval.
- Added exact-resubmission idempotency proof and service-principal denial proof; admitted tasks
  expose packet SHA-256 digests and remain `waiting_approval` until separately approved.
- Added durable immutable specification submission with sequential versions, founder-only
  digest-bound approve/reject, idempotency, and tamper detection before approval and planning.
- Added deterministic non-executable task drafting from approved specs: bounded paths, exact commit,
  typed gate commands, stable graph/task digests, unresolved-question blocking, and required
  independent review.
- Drafting intentionally emits one atomic delivery task until verified task-branch integration and
  merge arbitration exist; downstream QA must not run against the original pre-change base commit.
- Proved drafted packets feed atomic graph admission while creating no tasks during preview/drafting.

## Deployment truth

- Render staging and AlphaMeet were online at deployed revision `1e42c62` during pre-change audit.
- Current local fixes are **not pushed and not deployed**.
- Deployed service therefore does not yet contain translation endpoint auth/XSS repairs.
- No production deployment, migration, or GitHub push occurred.

## Open product gaps

1. Real Gemini 3.5 Live Translate audio proof is still open. Deterministic wiring tests do not prove provider audio.
2. Translator source/target participant isolation and feedback-loop prevention need a real multi-language room proof.
3. Meeting-to-durable-spec pipeline, consent/retention, and cross-network TURN proof remain open.
4. Temporal durable workflow, full agent adapters/router, client portal, AgentLine calls, deployment/rollback, and production hardening remain incomplete.
5. Credential values previously copied into Antigravity chat history should be rotated before broader production use.
6. Configured-model requirement decomposition/refinement remains open. Current safe lane creates a
   deterministic task graph from approved typed requirements without trusting free-form model output.
7. Client co-approval, spec editing/version UI, and mandatory spec binding on legacy direct-task
   submissions remain open.
8. Multi-task code decomposition remains blocked on verified result-commit integration/merge
   arbitration. Current planner safely keeps implementation and QA in one bounded packet.

## Safe next order

1. Review and commit local approved-spec planning packet.
2. With separate founder approval, push and deploy only to staging.
3. Add verified result-commit integration and merge arbitration with conflict/rollback proof.
4. Add model decomposition behind strict typed draft validation; model output never writes tasks.
5. Prove one small external project flow: approved spec, draft graph, atomic admission, execution
   approvals, worker, QA, review, and preview.
6. Run authenticated founder and invite-client endpoint smoke tests against staging.
7. Run real two-language LiveKit room proof with audio capture evidence and feedback-loop checks.
8. Continue transcript-to-spec traceability only after meeting evidence passes.
