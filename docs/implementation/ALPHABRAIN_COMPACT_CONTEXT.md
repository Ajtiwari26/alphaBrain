# AlphaBrain Compact Execution Context

## CURRENT SNAPSHOT — 2026-09-07 (read this section only for routine status)

Source: Verified `main` branch at `1669c21` after full autonomous delivery and merge of `NEXT-R2A` and `NEXT-R2B`.

**Decision: R2 (Mandatory Authenticated Review, Promotion Authorization, and Replay Defense) is FULLY VERIFIED and MERGED into main. Roadmap advances to R3.**

Verified deliveries in R2:
1. **NEXT-R2A (Enforceable Promotion Authorization & Checkout Validation)**:
   - Fixed dead-code indentation in `alpha_core/triage_cli.py` (`cmd_merge`).
   - Enforced 7 independent fail-closed checks before acquiring promotion locks or running mutating Git commands (valid signature, matching task ID, matching base commit, matching result SHA, consensus verdicts `pro_verdict == 'APPROVE'` / `opus_verdict == 'FINAL_APPROVAL'`, and matching `evidence_digest`).
   - Zero-Git mutation invariant: all invalid promotion attempts fail-closed with 0 Git ref/worktree mutations.
   - Removed default signing key fallback from `alpha_worker/senior_review_engine.py` (missing secret strictly halts review before model execution).
   - Enforced mandatory reviewer checkout validation (missing worktree, git error, dirty working tree, or HEAD mismatch strictly raises `ValueError`).
2. **NEXT-R2B (Cryptographic Provenance, Expiry TTL, Replay Nonce & Principal Separation)**:
   - Upgraded `ReviewAttestation` to explicit `schema_version: '2.0'`.
   - Principal separation: `executor_id != reviewer_id` enforced at Pydantic model validator and merge gate.
   - Temporal TTL: `issued_at` and `expires_at` validated at deserialization; expired attestations fail-closed.
   - Replay attack defense: unique `nonce` bound to cryptographic attestation and persisted in `.alphabrain/seen_nonces.txt`. Replays immediately rejected.
   - Key management: `key_id` bound to attestation; revoked keys (`ALPHA_REVOKED_KEYS`) rejected.
   - Tree digest: `tree_digest` (Git tree SHA) bound to attestation and validated against branch tip tree.
   - Robust terminal protocol parsing in `alpha_worker/adapters/antigravity_live.py` supporting markdown formatting and resumed conversation tokens.
   - Executed through AlphaBrain's autonomous self-development pipeline (`admit` $\rightarrow$ `review` $\rightarrow$ `approve` $\rightarrow$ `worker-cycle` $\rightarrow$ `senior-review` $\rightarrow$ `merge`) with 2-round senior review debate and autonomous repair turn.

Verified local evidence:
- Full test suite: **703 passed, 11 skipped, 0 failed** in 56.44s via pytest (`--runxfail`).
- Ruff lint & format: clean (0 diagnostics, 223 files compliant).
- Mypy static typing: 0 errors across 61 source files.

Remaining gaps in roadmap:
- R3: Mandatory 4-tuple lease fencing on every queue mutation (`worker_id`, `lease_id`, `fencing_epoch`, `attempt_id`).
- R4: Crash-safe atomic promotion with target revision verification.
- R5: Meaningful verification profiles & cumulative repair budget limits.
- R6: Real integrated autonomous proof without mocks.

---

## Archived context — 2026-08-31

Last updated: 2026-08-31

Purpose: canonical low-token context for Codex senior supervision and AGY junior execution. Read this file, current packet, `git diff`, and Code Review Graph results. Do not reload old chats unless an exact historical artifact is missing.

## 1. Product goal

AlphaBrain is DeployMate's orchestration brain. It must turn approved client requirements into safe project delivery while keeping founder control and truthful evidence.

Target flow:

1. Eva/AlphaMeet captures client discussion and produces structured requirements.
2. Founder approves immutable specification.
3. AlphaBrain creates bounded task graph.
4. Outbound Mac worker executes approved tasks through AGY in isolated Git worktrees.
5. Automated gates and independent review verify results.
6. Founder separately approves source-repository promotion and deployment.
7. Client/founder portal shows evidence, progress, blockers, previews, and audit history.
8. AgentLine calls founder only for verified urgent decisions or reviews.
9. Render control plane and Supabase retain durable truth; Mac worker can disconnect and recover without duplicate execution.

Priority: project-completion capability first. Meeting polish, calls, portal, and broader automation follow after autonomous delivery proof.

## 2. Component ownership

- `alpha_core/`: API, durable state engine, approvals, audits, scheduler, reporting, DB readiness.
- `alpha_protocol/`: signed/canonical request, result, gate, checkpoint, worker, and promotion contracts.
- `alpha_worker/`: outbound Mac worker, AGY execution, encrypted spool, worktrees, previews, recovery.
- `alpha_meet/`: AlphaMeet frontend/backend and Eva meeting integration.
- `alpha_voice/`: voice/telephony integration.
- `alpha_protocol/`, `alpha_worker/`, `alpha_core/` form autonomous project kernel.
- `testscript/`: all tests, harnesses, evidence helpers, and temporary test tooling. Keep repository root clean.
- Client projects live outside AlphaBrain under `/Users/ajaytiwari/Desktop/Projects/clientProjects/<project>`; AlphaBrain stores references, not client source inside its own codebase.

## 3. Current verified repository state

Main local head before current packet:

- `c7f3df1` — approved spec task planning lane.
- `f18557c` — atomic approved task graph admission.
- `4e42ee8` — AlphaMeet translation hardening and restored quality gates.

Remote `origin/main` currently lags local main at `1e42c62`. No push/deploy is implied by local commits.

Current H4 branch:

- Branch: `alpha/h4-result-promotion`
- Commit: `9c78f9e` — founder-approved result promotion pipeline.
- Base: `c7f3df1993704ae867bd2614f0b860c329640153`.
- User-owned untracked file: `alpha_meet/frontend/.gitignore`. Preserve untouched and never stage automatically.

H4 still requires independent senior verification after AGY commit. AGY self-report is not acceptance.

## 4. Capabilities already proven or materially implemented

Evidence-backed local/staging work completed across earlier packets:

- Durable task state, leases, attempts, approvals, gate evidence, audits, checkpoints, retries, cancellation, recovery, and reports.
- Approved spec -> bounded atomic task admission -> worker lease path.
- Outbound Mac worker with signed identity bootstrap/refresh, encrypted result spool, launchd operation, and local recovery harness.
- Watchdog/recovery moved out of lease hot path; PostgreSQL `FOR UPDATE SKIP LOCKED` concurrency proofs added.
- Supabase staging schema migrated to Alembic head `58b5b056d9e3`; downgrade/upgrade cycle tested in disposable PostgreSQL.
- Render staging configuration hardened: manual deploy, `/health/ready`, no startup migrations.
- AlphaMeet/Eva local duplex meeting slice and later AlphaMeet deployment work exist, but deployed meeting claims require fresh endpoint/browser/provider verification before calling production-complete.
- QA/security gates have repeatedly blocked out-of-scope AGY edits; this is expected safety behavior, not project failure.

Truth rule: distinguish `implemented`, `local verified`, `staging verified`, `production verified`, `partial`, and `blocked`. Never upgrade status without direct evidence.

## 5. Current packet: H4 result promotion

Problem: worker can produce a verified result commit on `alpha/<task_id>`, but source repository must not change until founder separately approves exact promotion digest.

Required authority chain:

1. Task execution approval authorizes work only.
2. Task review approval authorizes verified result only.
3. Separate `task_promotion` approval binds exact task, project, attempt, worker, repo, base commit, result commit, sorted changed files, and review digest.
4. Producing worker alone fetches approved promotion.
5. Worker validates repository and performs only `git merge --ff-only <result_commit>`.
6. Deployment remains separate and requires separate founder approval.

Required Git invariants:

- Source repo tracked-clean (`git status --porcelain --untracked-files=no`); unrelated untracked user files preserved byte-for-byte; colliding untracked files rejected by git merge with HEAD unchanged.
- HEAD equals exact base, or exact result for crash recovery.
- Base/result resolve; base is ancestor of result.
- `refs/heads/alpha/<task_id>` exists and points exactly to result.
- Actual diff files exactly equal persisted attempt files.
- Every changed file is allowed.
- Already-at-result recovery still performs every read-only validation.
- No rebase, cherry-pick, force, conflict repair, branch deletion, push, or auto-deploy.

Required result behavior:

- PromotionRequest and digest validation occurs strictly before mutating review approval or task state; validation failure fails closed (leaves task VERIFIED, review PENDING, zero task_promotion approvals, zero completion/promotion audit events).
- Callback authenticates exact approved promotion, attempt, approved review, digest, and producing worker.
- Success replay is idempotent only for matching digest/worker/audit.
- Failure is terminal; no automatic mutation retry.
- Unavailable acknowledgement uses existing encrypted spool and replays before new promotion fetch.
- Corrupt protocol or unexpected local error fails closed.

Primary design packet: `docs/implementation/AGY_H4_RESULT_PROMOTION_PACKET.md`.

## 6. Next roadmap after H4 acceptance

1. H5 autonomous self-development proof:
   - Select one low-risk AlphaBrain TODO.
   - Generate bounded spec/task through control plane.
   - Founder approves execution.
   - AGY builds in isolated worktree.
   - Gates and review verify.
   - Founder approves H4 promotion.
   - No deployment unless separately approved.
2. Repeat proof on one small external client fixture project.
3. Complete robust specification pipeline from Eva notes to approved structured spec.
4. Founder/client portal for truthful status, evidence, blockers, approvals, and preview.
5. AgentLine verified calls for urgent decisions and review guidance.
6. Preview-first deployment pipeline; production only after founder approval.
7. Render/Supabase durability, backup/restore, privacy, uptime reporting, and pilot hardening.
8. Future external always-on supervisor/VPS may wake Mac, track uptime/downtime, resume work, and trigger calls; keep as future work until core delivery loop is proven.

## 7. Senior/junior operating model

Codex role: senior engineer and supervisor.

- Define architecture, acceptance criteria, bounded packet, reject conditions, and evidence gates.
- Inspect live AGY diff early; interrupt on authority drift or unsafe scope.
- Independently verify after AGY exits.
- Do not duplicate junior implementation unless user explicitly requests Codex coding.

AGY role: junior executor.

- Read this compact context, current packet, Code Review Graph query, and current diff.
- Implement one bounded packet.
- Use only allowed paths.
- Keep test artifacts under `testscript/`.
- Stop after local commit and exact gate report.

Model routing:

- Gemini 3.1 Pro High: architecture-heavy or difficult coding.
- Gemini 3.7 Flash High: mechanical repair, test cleanup, fast execution.
- Claude Sonnet/Opus: scarce; use only short independent design/review when value exceeds quota cost.
- Codex tokens: senior review and independent verification, not routine labor.

## 8. Non-negotiable safety and quality rules

- Never expose, log, commit, or repeat secrets. Rotate exposed secrets when risk exists.
- No push, merge to main, Render deploy, Supabase migration, production mutation, package install, reset, stash, or clean without explicit current authorization.
- No direct database mutation in hermetic tests.
- No production worker interruption unless packet explicitly authorizes bounded proof.
- Use real temp Git repositories for Git safety tests.
- Required gates: focused tests, full pytest, Ruff check, Ruff format check, Mypy, bounded `git diff --check`, clean status except preserved user files.
- Claims require exact outputs. Passing unit tests alone does not prove browser, voice, RTC, provider, deployment, or production flow.

## 9. Context retrieval protocol

For future AGY/Codex turns:

1. Query Code Review Graph for changed symbols and impact.
2. Read this file.
3. Read only current packet.
4. Inspect `git status`, base..HEAD diff, and relevant tests.
5. Do not load old chat transcript unless these sources lack a required decision.

Known useful AGY chats:

- Historical supervisor chat: `8f2a55c1-30ae-4bfc-bb2f-60759025fe13`.
- Earlier master-plan chat identifier reported by prior tooling: `1c2faacb-9183-4e88-b718-51fba0f9c9ef`; treat as historical only.
- H4 initial/rework chat: `80c09b92-2f4f-4aa3-8612-b1362e6c2426`.
- H4 fresh repair chat: `afa274bc-2d31-4e81-aa4d-594652da5a4e`.

This document supersedes conversational summaries when they conflict with current code, current packets, or direct verification.
