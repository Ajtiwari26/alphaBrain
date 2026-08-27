# AlphaBrain AGY Future Implementation Master Plan

**Authority:** senior-engineer execution contract  
**Executor:** AGY CLI / Antigravity 2.0  
**Primary model:** `gemini-3.1-pro-high`, effort `high`  
**QA model:** `gemini-3.7-flash-high`  
**Independent reviewer:** `claude-sonnet-4-6` only when quota is available  
**Timebox:** approximately 150 minutes  
**Production side effects:** forbidden during this run

## 1. Mission

Finish the smallest safe AlphaBrain capability that can implement, verify, reject, and retry one
of its own low-risk tasks through the real autonomous project kernel. Do not broaden into Eva,
AgentLine, portal, production deployment, or full P7-P13 work during this run.

This document is execution authority. AGY may inspect code and report conflicts, but it must not
replace this design with a new roadmap. Each packet must pass its gate before the next starts.

## 2. Current verified baseline

Treat only these facts as accepted:

- P6-R1 deterministic model/account selector exists under
  `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/`.
- P6-R1 focused proof passed 15 tests, compile, Ruff, format, and skill validation.
- P6-R1 is selector-only. It does not yet switch accounts or control AlphaBrain runtime.
- Five OAuth profiles exist, but a valid refresh token does not prove model quota.
- D1-2 state-engine contract repair passed 27 focused tests plus Ruff, format, and mypy.
- Current source repository is dirty. Never clean, stash, reset, commit, merge, or delete founder
  work automatically.
- Render and Supabase CLIs are authenticated, but production deployment and database wiring remain
  unverified and outside this run.
- Repository-wide green status is not established. Focused packet gates cannot be described as a
  full-repository pass.

Disclosed historical side effect: a previous AGY run installed user-level PyYAML 6.0.3 despite a
no-install rule. Do not install, uninstall, or upgrade dependencies in this run.

## 3. Target architecture

```text
Frozen TaskEnvelope
  -> explicit execution stage, risk, allowed models, Claude budget
  -> deterministic RoutingRequest
  -> non-secret RouterDecision(model, effort, account, fallback, independence)
  -> acquire global credential lease
  -> switch exact profile at process boundary
  -> verify sanitized active identity
  -> launch one AGY process with explicit model and effort
  -> retain lease for full AGY process lifetime
  -> parse exit, timeout, cancellation, auth failure, or rate limit
  -> record sanitized per-account/per-model outcome atomically
  -> produce typed attempt/evidence result
  -> supervisor independently verifies gates and diff
  -> accept, reject, or create bounded repair attempt
```

### 3.1 Required contracts

`RoutingRequest`:

- `project_id`, `task_id`, `attempt_id`;
- `stage`: `plan`, `implement`, `review`, `qa`, or `mechanical`;
- `risk_class`, `complexity_class`;
- `implementation_model` for review routing;
- exact `allowed_models`;
- `claude_budget_allowed` defaulting to false;
- required capabilities and tool needs.

`RoutingDecision`:

- `status`: `selected`, `rate_limited`, or `blocked`;
- exact `model`, `effort`, and non-secret `account_id` when selected;
- machine-readable `rationale_codes`;
- valid remaining `fallback_chain`;
- `independence_status` and `founder_review_required`;
- `earliest_retry_at` and `retry_timestamp_known` when unavailable.

`AccountModelState` contains metadata only:

- `unknown`, `available`, `cooldown`, `auth_failed`, or `disabled`;
- last selection/success/failure/rate-limit timestamps;
- next eligibility and timestamp source;
- sanitized failure class and rolling outcome counters.

Never store OAuth/access/refresh tokens, Keychain data, raw provider payloads, prompts, or command
output containing secrets.

### 3.2 Concurrency invariant

Account switching mutates shared machine state. One global inter-process lock must cover:

1. selection recheck;
2. exact profile switch;
3. sanitized identity verification;
4. full AGY subprocess lifetime;
5. outcome recording.

Use crash-released OS file locking such as `fcntl.flock`. Never force-delete a lock file. A lock
timeout becomes a typed retryable result. No account switch may occur inside an active AGY
conversation/process.

### 3.3 Retry invariant

- At most one full eligible-profile cycle per logical task attempt.
- One account/model pair may run once in that cycle.
- 429/rate-limit records cooldown for exact account/model, then creates a new execution attempt.
- Explicit provider reset timestamp wins. Missing timestamp uses configured five-hour fallback
  labeled `configured_fallback`, never provider-confirmed.
- Auth failure disables exact profile until manual reauthentication.
- Exhausted pool returns truthful `RATE_LIMITED`; never spins forever.
- Same-family review is `degraded`, requires founder review, and cannot be labeled independent.

## 4. Global execution rules

AGY must obey every rule for every packet:

1. Read this file plus referenced architecture before editing.
2. Emit a maximum-five-line implementation note; do not spend time recreating roadmap.
3. Use `code-review-graph` before edits and after edits when available. Tool absence is disclosed,
   not fabricated.
4. Modify only packet allowlist. Existing unrelated dirty files remain untouched.
5. No dependency install, network fetch, profile probing, production database mutation, deploy,
   Git commit, push, merge, reset, stash, or cleanup.
6. Keep tests inside `testscript/`.
7. Run exact packet commands and capture exit codes.
8. Never infer success from model prose, quiet process, changed files, or partial tests.
9. Stop immediately on scope conflict, unsafe shared-auth state, secret exposure, or unkillable
   process group.
10. Emit one terminal manifest. Success token is permitted only after every required gate passes.

## 5. Model use for this run

| Work | Model | Rule |
|---|---|---|
| Runtime contracts, locking, state, bridge integration | `gemini-3.1-pro-high` | Default, effort high |
| Focused test expansion, formatting, mechanical repair | `gemini-3.7-flash-high` | No architecture changes |
| Independent final diff review | `claude-sonnet-4-6` | Read-only, one bounded turn |
| Opus planning | Do not use | Senior design is already frozen |

Silent fallback is forbidden. Every attempt records selected model, effort, non-secret account ID,
reason, and outcome. If requested model has no eligible account, return blocked/rate-limited so
supervisor can choose declared fallback.

## 6. 150-minute packet schedule

Time is budget, not permission to skip gates. Finish current packet before starting next.

| Window | Packet | Goal |
|---|---|---|
| 0-15 min | R2-0 | Read-only orientation and frozen change map |
| 15-50 min | R2-A | Runtime routing contracts and configuration |
| 50-90 min | R2-B | Global credential lease and switch boundary |
| 90-125 min | R2-C | AGY bridge integration and bounded outcome retry |
| 125-145 min | R2-D | Adversarial QA and focused regression proof |
| 145-150 min | R2-E | Evidence manifest and next-run handoff |

If a packet blocks, use remaining time for diagnosis and a narrow repair inside same allowlist.
Do not jump ahead around a failed foundation.

## 7. Packet R2-0 — orientation and change map

### Objective

Confirm exact insertion points without editing. Return concise map of current types, launch path,
state persistence, and tests. Identify conflicts between this design and current code.

### Read-only files

- `docs/architecture/agy-model-account-routing-audit.md`
- `docs/architecture/agy-junior-execution-contract.md`
- `docs/architecture/autonomous-project-kernel.md`
- `docs/architecture/self-development-control-loop.md`
- `alpha_protocol/task.py`
- `alpha_core/config.py`
- `alpha_worker/adapters/antigravity.py`
- `alpha_worker/adapters/antigravity_live.py`
- `alpha_worker/daemon.py`
- `testscript/test_antigravity_live_bridge.py`
- `testscript/test_agy_execution_result.py`
- `testscript/test_adapter_conformance.py`
- `testscript/test_worker_runtime.py`
- router skill files under `~/.gemini/config/skills/alphabrain-model-router/`

### Acceptance

- No files changed.
- No account switched or probed.
- Output names concrete functions/types and proposes allowlist for R2-A through R2-D.
- Any unknown contract is marked unknown instead of guessed.

### Copy-paste prompt

```text
You are AGY junior executor. Work in /Users/ajaytiwari/Desktop/Projects/alphaBrain.
Read docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md completely, then execute only
Packet R2-0. This is read-only orientation. Do not edit, install, switch accounts, invoke provider
requests, deploy, commit, push, stash, reset, or clean. Use Gemini 3.1 Pro High with high effort.
Return exact insertion points, current signatures, conflicts, proposed per-packet allowlists, and
blockers in at most 80 lines. Do not redesign roadmap.
```

## 8. Packet R2-A — routing contracts and config

### Objective

Add typed, additive runtime contracts for stage/request/decision/account outcome and guarded config
for router integration. Default feature flag must keep current launch behavior unchanged.

### Expected files

- `alpha_protocol/task.py` or a focused new `alpha_protocol/routing.py`;
- `alpha_protocol/__init__.py` only for explicit exports;
- `alpha_core/config.py`;
- one focused runtime routing module under `alpha_worker/`;
- `testscript/test_model_routing_runtime.py`.

R2-0 may narrow names, but may not broaden beyond these areas without blocking.

### Required behavior

- Strict enums and validation; unknown stage/model/state fails closed.
- Feature flag defaults off.
- Explicit router state path, lock path, lock timeout, inferred cooldown, and max eligible attempts.
- No credentials in protocol objects.
- Existing TaskEnvelope fixtures remain backward compatible through safe defaults.
- Runtime wrapper consumes router selector through stable function/subprocess boundary; it must not
  import OAuth internals.
- Selector decision alone has no account-switch or network side effect.

### Gates

```bash
# Run focused runtime routing contract tests.
./.venv/bin/pytest -q testscript/test_model_routing_runtime.py testscript/test_protocol_v1.py

# Check lint for packet files.
./.venv/bin/ruff check alpha_protocol alpha_core/config.py alpha_worker testscript/test_model_routing_runtime.py

# Verify packet formatting without modifying unrelated files.
./.venv/bin/ruff format --check alpha_protocol alpha_core/config.py alpha_worker testscript/test_model_routing_runtime.py

# Type-check runtime files touched by packet.
./.venv/bin/mypy alpha_protocol alpha_core/config.py alpha_worker

# Detect whitespace errors in current diff.
git diff --check
```

### Reject

- Breaking existing task payloads without migration/version plan.
- Hard-coded personal email addresses in source.
- Feature enabled by default.
- Router error silently falls back to global model.
- Test mocks that assert only function was called but not exact decision fields.

### Copy-paste prompt

```text
Execute only Packet R2-A from docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md.
Use Gemini 3.1 Pro High, effort high. Treat R2-0 map as context, this document as authority.
Make smallest additive implementation. Preserve all unrelated dirty work. No installs, network,
account switch, deploy, commit, push, stash, reset, or cleanup. Run every R2-A gate exactly. If one
fails, repair only within allowlist and rerun. Stop after one bounded repair pass. Return terminal
manifest; never emit success when any gate or allowlist check is missing.
```

## 9. Packet R2-B — global credential lease

### Objective

Implement safe serialized profile switching as a replaceable executor. Unit tests use fake commands,
fake profiles, temporary state, and concurrent processes/threads. No real profile changes in tests.

### Expected files

- focused module such as `alpha_worker/agy_credentials.py`;
- `alpha_core/config.py` only if R2-A did not finish settings;
- `testscript/test_agy_credential_lease.py`.

### Required behavior

- `fcntl.flock` or equivalent crash-released inter-process lock.
- Configurable bounded lock timeout.
- Switch command receives exact non-secret account ID through argv list, never shell string.
- Sanitized identity verifier must confirm expected account before launch.
- Lease remains held through child process lifetime; API must make early release difficult.
- Exception, cancellation, timeout, and child crash release OS lock.
- Logs redact email if policy requires, and always redact tokens/raw output.
- Malformed state fails closed. No deletion or forced unlock.
- Dependency-injected runner makes all tests offline and prevents Keychain/profile mutation.

### Adversarial tests

- Two contenders cannot enter critical section together.
- Timeout returns typed `credential_lock_timeout`.
- Wrong active identity blocks launch.
- Switch nonzero exit blocks launch and records sanitized `auth_failed` only when classification is
  reliable.
- Exception and cancellation release lock.
- Token-like fake stdout/stderr never reaches returned error or ledger.
- Command injection characters in account ID fail validation.

### Gates

```bash
# Run credential lease and routing tests.
./.venv/bin/pytest -q testscript/test_agy_credential_lease.py testscript/test_model_routing_runtime.py

# Lint and format-check packet files.
./.venv/bin/ruff check alpha_worker/agy_credentials.py alpha_core/config.py testscript/test_agy_credential_lease.py
./.venv/bin/ruff format --check alpha_worker/agy_credentials.py alpha_core/config.py testscript/test_agy_credential_lease.py

# Type-check credential boundary.
./.venv/bin/mypy alpha_worker/agy_credentials.py alpha_core/config.py

# Detect whitespace errors.
git diff --check
```

### Reject

- Lock released immediately after switch and before AGY exits.
- `shell=True`, interpolated shell command, or unvalidated account identifier.
- Unit test touches real token, Keychain, account pointer, or provider.
- Blind probing of all five accounts.
- Lock file force deletion.
- Secret/raw response persisted or printed.

### Copy-paste prompt

```text
Execute only Packet R2-B from docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md.
Use Gemini 3.1 Pro High, effort high. Implement serialized credential lease with dependency-injected
fake switch/identity runners. Never touch real accounts during tests. Preserve unrelated dirty work.
No installs, network, deploy, commit, push, stash, reset, or cleanup. Run all R2-B gates. One bounded
repair pass only; repeated failure becomes exact BLOCKED result.
```

## 10. Packet R2-C — bridge integration and outcome ledger

### Objective

Replace global-only AGY model launch with explicit per-attempt decision while preserving disabled
feature behavior. Integrate routing, credential lease, AGY process, sanitized outcome record, and
bounded retry scheduling.

### Expected files

- `alpha_worker/adapters/antigravity_live.py`;
- `alpha_worker/adapters/antigravity.py`;
- `alpha_worker/daemon.py` only if retry scheduling belongs there;
- R2-A/R2-B focused modules;
- `testscript/test_antigravity_live_bridge.py`;
- `testscript/test_agy_execution_result.py`;
- `testscript/test_adapter_conformance.py`;
- `testscript/test_worker_runtime.py`;
- new `testscript/test_agy_routed_execution.py`.

### Required behavior

- `_run_agy` or successor receives explicit selected model and effort; no hidden environment
  fallback when routing feature is enabled.
- Persist selected model, effort, non-secret account ID, decision reason, and attempt lineage.
- Credential lease covers full `Popen` lifecycle.
- Cancellation still terminates full process group.
- Exit 0 plus completion prose is not task acceptance; typed gates remain required.
- Nonzero exit, timeout, cancellation, auth failure, malformed output, and 429 map distinctly.
- 429 updates exact account/model cooldown and schedules at most remaining eligible profiles.
- One full eligible-profile cycle maximum. No recursive/unbounded retry.
- Feature flag off preserves accepted old path and existing tests.
- No review independence claim when implementer and reviewer share provider family.

### Gates

```bash
# Run full adapter, routed-execution, worker, and state regression slice.
./.venv/bin/pytest -q testscript/test_antigravity_live_bridge.py testscript/test_agy_execution_result.py testscript/test_adapter_conformance.py testscript/test_worker_runtime.py testscript/test_agy_routed_execution.py testscript/test_state_engine.py testscript/test_api_and_workflow.py

# Lint packet runtime and tests.
./.venv/bin/ruff check alpha_worker alpha_protocol alpha_core/config.py testscript/test_antigravity_live_bridge.py testscript/test_agy_execution_result.py testscript/test_adapter_conformance.py testscript/test_worker_runtime.py testscript/test_agy_routed_execution.py

# Check formatting without broad rewrites.
./.venv/bin/ruff format --check alpha_worker alpha_protocol alpha_core/config.py testscript/test_antigravity_live_bridge.py testscript/test_agy_execution_result.py testscript/test_adapter_conformance.py testscript/test_worker_runtime.py testscript/test_agy_routed_execution.py

# Type-check runtime integration.
./.venv/bin/mypy alpha_worker alpha_protocol alpha_core/config.py

# Detect whitespace and conflict markers.
git diff --check
```

### Reject

- Account switch after AGY process begins.
- Result says verified solely because AGY exited 0 or printed `ALPHA_BRAIN_TASK_DONE`.
- 429 mapped to generic success/failure without cooldown metadata.
- Retry can revisit same pair endlessly.
- Global default silently used after router error.
- Existing cancellation/process-group behavior regresses.
- Changes outside allowlist or unrelated cleanup/refactor.

### Copy-paste prompt

```text
Execute only Packet R2-C from docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md.
Use Gemini 3.1 Pro High, effort high. Integrate routing decision and credential lease into AGY
process boundary. Preserve feature-off behavior and process-group cancellation. Use fake accounts
and fake subprocesses only. No live account switching or provider probes. No installs, network,
deploy, commit, push, stash, reset, or cleanup. Run every R2-C gate. One bounded repair pass; then
return DONE with evidence or BLOCKED with exact failing contract.
```

## 11. Packet R2-D — independent adversarial QA

### Objective

Review only. Seed no permanent defects. Attempt to disprove safety and truthfulness of R2 work.

### Reviewer routing

1. Prefer `claude-sonnet-4-6` for one read-only bounded review if available.
2. If unavailable, use `gemini-3.7-flash-high`, mark review `degraded_same_family=true`, and require
   founder/senior review.
3. Do not use Opus for this packet.

### Review checklist

- lock lifetime and crash release;
- race between selection, switch, and launch;
- active identity mismatch;
- secret leakage through errors/logs/ledger;
- malformed ledger and atomic write failure;
- 429 reset source truth;
- exhausted pool and retry bound;
- cancellation kills process group;
- feature-off compatibility;
- same-family review truth;
- path boundary and no production/network side effects;
- evidence cannot be forged from model text.

### QA command

```bash
# Re-run complete P6-R2 regression slice after review findings are resolved.
./.venv/bin/pytest -q testscript/test_model_routing_runtime.py testscript/test_agy_credential_lease.py testscript/test_antigravity_live_bridge.py testscript/test_agy_execution_result.py testscript/test_adapter_conformance.py testscript/test_worker_runtime.py testscript/test_agy_routed_execution.py testscript/test_state_engine.py testscript/test_api_and_workflow.py

# Run final lint, formatting, typing, and diff checks for touched scope.
./.venv/bin/ruff check alpha_worker alpha_protocol alpha_core/config.py testscript
./.venv/bin/ruff format --check alpha_worker alpha_protocol alpha_core/config.py testscript
./.venv/bin/mypy alpha_worker alpha_protocol alpha_core/config.py
git diff --check
```

If broad `testscript` Ruff/format exposes pre-existing unrelated errors, report exact baseline versus
packet findings. Do not edit unrelated files to manufacture green status.

### Copy-paste prompt

```text
Perform Packet R2-D from docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md as read-only
adversarial reviewer. Prefer Claude Sonnet 4.6 for independent family; if unavailable use Gemini
3.7 Flash High and explicitly mark review degraded. Inspect exact diff and attempt to falsify lock,
identity, retry, secret-redaction, cancellation, compatibility, and evidence claims. Do not edit.
Return findings ordered critical/high/medium/low with exact file and line. Return PASS only when no
unresolved critical/high finding exists and exact QA command evidence is present.
```

## 12. Packet R2-E — repair and evidence closeout

Implementation model repairs only accepted reviewer findings. One focused repair pass. Re-run exact
affected tests plus complete R2-D QA command. Do not start a second feature.

Required final manifest:

```json
{
  "contract_version": 1,
  "packet_ids": ["P6-R2-A", "P6-R2-B", "P6-R2-C", "P6-R2-D"],
  "status": "DONE_OR_BLOCKED",
  "base_revision": "EXACT_GIT_SHA",
  "changed_files": [],
  "models_used": [],
  "account_ids_used": [],
  "commands": [
    {"argv": [], "exit_code": 0, "summary": "sanitized exact result"}
  ],
  "tests": {"passed": 0, "failed": 0, "scope": "focused_or_repository"},
  "ruff": "PASS_OR_EXACT_FAILURE",
  "format": "PASS_OR_EXACT_FAILURE",
  "mypy": "PASS_OR_EXACT_FAILURE",
  "review": {
    "model": "EXACT_MODEL",
    "independent": false,
    "degraded_same_family": false,
    "open_high_findings": 0
  },
  "routing_proof": {
    "real_account_switch_performed": false,
    "fake_concurrency_proof": "PASS_OR_FAIL",
    "bounded_retry_proof": "PASS_OR_FAIL",
    "secret_scan": "PASS_OR_FAIL"
  },
  "side_effects": [],
  "blockers": [],
  "next_packet": "P6-R3 controlled live proof"
}
```

Emit `ALPHA_BRAIN_TASK_DONE` only after manifest and all gates pass. Otherwise emit
`ALPHA_BRAIN_TASK_BLOCKED: <exact reason>`.

## 13. Acceptance, rejection, and retry policy

### Accept P6-R2 only when

- Every expected behavior has executable evidence.
- All changed paths fit approved packet allowlists.
- Focused regression suite passes with exact count and exit code.
- Ruff, format check, mypy, and `git diff --check` pass for touched scope.
- Fake concurrency test proves mutual exclusion.
- Tests prove no real token/profile/provider interaction.
- Retry count is structurally bounded.
- No unresolved critical/high reviewer finding remains.
- Review independence is labeled truthfully.
- Feature remains disabled by default.

### Reject immediately when

- AGY changes, deletes, cleans, stashes, commits, pushes, merges, or deploys unrelated work.
- AGY installs dependencies or calls provider/network without packet permission.
- Tests touch real account state.
- Secrets or raw OAuth/provider payloads appear in source, log, result, or ledger.
- Lock does not cover full process lifetime.
- Same account/model can retry forever.
- Success derives from prose, quiet time, exit 0, or preview alone.
- Missing evidence is represented as pass.
- Same-family review is labeled independent.
- Render/Supabase production work begins before P6-R2 acceptance.

### Retry rules

| Failure | Action | Limit |
|---|---|---|
| Ruff/format-only | Flash High mechanical repair | 1 pass |
| Focused behavior test | Pro High narrow repair in same conversation | 1 pass |
| Same failure repeats | Stop `BLOCKED`, preserve evidence | No third attempt |
| New regression caused by repair | Revert only AGY packet edit if safely isolated; otherwise stop | 1 evaluation |
| 429 | Record exact cooldown; next eligible profile on new attempt | One pool cycle |
| Auth failure | Disable exact profile pending manual reauth | No auto-retry |
| Lock timeout | Retry after bounded backoff | 1 retry |
| Identity mismatch | Stop; never launch AGY | No auto-fix |
| Malformed/corrupt ledger | Fail closed and preserve file for diagnosis | No reset/delete |
| Reviewer critical/high finding | Pro High focused repair, then independent rereview | 1 repair |
| Missing reviewer quota | Mark degraded and require senior/founder review | No fake independence |

## 14. What follows after P6-R2

Do not execute these during current 150-minute packet unless senior explicitly authorizes next run.

### P6-R3 — controlled live routing proof

- Use one harmless read-only AGY prompt.
- Snapshot active account identity before run.
- Select one known eligible profile, acquire global lease, switch, verify, launch, and record.
- Prove no concurrent process can switch identity.
- Restore previous profile only as an explicit, separately recorded cleanup action.
- No project code change, no deployment.

### D2 — one low-risk AlphaBrain self-task

- First establish immutable clean baseline through founder-approved repository action.
- Freeze one docs/test-only TODO packet.
- Run admission, approval, lease, isolated worktree, routed AGY execution, typed gates, independent
  review, and founder decision.
- Never auto-merge result into source.

### External-project proof

- New project directory outside AlphaBrain under approved client-project root.
- Requirement -> frozen DAG -> AGY build -> deterministic QA -> local preview -> founder review.
- No direct senior/manual repair inside client project; rejected result returns through kernel.

### Staging infrastructure

- Deploy Render control plane with AGY execution disabled.
- Connect Supabase Postgres using pooled `DATABASE_URL`.
- Run migration upgrade and rollback proof in staging.
- Register outbound Mac worker; prove restart/recovery and duplicate prevention.
- Redis remains unnecessary until distributed locking, high-volume queueing, or rate limiting needs
  it.

### Later roadmap order

1. P9 specification pipeline: Eva transcript to versioned approved spec.
2. P11 founder/client portal: truthful state, evidence, blocker, and preview display.
3. P10 AgentLine calls: only verified urgent facts and approval requests.
4. P12 preview/deployment adapters: production requires founder approval.
5. P7/P13 durable workflow, privacy, backup/restore, security, and pilot hardening.

## 15. Master prompt for one AGY conversation

Use this when handing whole timebox to one existing AGY project conversation:

```text
Work as AlphaBrain junior executor in /Users/ajaytiwari/Desktop/Projects/alphaBrain.
Read docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md completely. This file is frozen
senior authority. Execute packets R2-0, R2-A, R2-B, R2-C, R2-D, and R2-E sequentially. Never skip
a failed gate or start later packet around a blocker. Use gemini-3.1-pro-high with high effort for
runtime implementation; use gemini-3.7-flash-high only for mechanical QA/format repair; request one
read-only claude-sonnet-4-6 independent review only if quota is available. Do not use Opus.

Preserve all unrelated dirty files. Never install/uninstall dependencies, probe or switch real
accounts, access raw tokens/Keychain payloads, deploy, mutate Supabase/Render, commit, push, merge,
stash, reset, clean, or delete files. Tests must use fake accounts, fake commands, temporary state,
and no network. Use code-review-graph before and after edits when available. Run every exact packet
gate and capture exit code. One bounded repair pass per packet; repeated same failure means BLOCKED.

After each packet print compact checkpoint: packet, changed files, commands with exit codes, gate
result, side effects, blockers, next packet. Final output must use Packet R2-E JSON manifest followed
by ALPHA_BRAIN_TASK_DONE only if every requirement passed. Otherwise print
ALPHA_BRAIN_TASK_BLOCKED with exact reason. Do not create a replacement plan.
```

## 16. Optional terminal launch

Run only after opening existing AlphaBrain AGY conversation or providing its conversation ID.

```bash
# Execute frozen P6-R2 master plan in one bounded AGY run; replace CONVERSATION_ID with existing AlphaBrain chat ID.
agy --conversation CONVERSATION_ID --model gemini-3.1-pro-high --effort high --mode accept-edits --dangerously-skip-permissions --print-timeout 150m -p "Read /Users/ajaytiwari/Desktop/Projects/alphaBrain/docs/implementation/AGY_FUTURE_IMPLEMENTATION_MASTER_PLAN.md completely and execute Section 15 exactly."
```

If installed AGY syntax differs, check `agy --help` read-only and change CLI flags only. Do not
weaken plan, permissions, gates, or stop conditions.
