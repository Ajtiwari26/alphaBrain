# AlphaBrain Post-D3-4 AGY Execution Pack

**Authority:** senior-engineer frozen design
**Executor:** AGY CLI through Antigravity 2.0
**Primary coding model:** `gemini-3.1-pro`, effort `high`
**Fast QA model:** `gemini-3.7-flash-high`
**Independent review:** `claude-sonnet-4-6` only when quota is available
**Opus use:** one read-only architecture dispute turn only; never implementation
**Repository:** `/Users/ajaytiwari/Desktop/Projects/alphaBrain`
**No automatic push, deploy, migration, or production mutation.**

## 1. Mission

Move AlphaBrain from locally proven worker/control-plane mechanics to one real, auditable,
recoverable autonomous coding loop. Preserve senior design. AGY performs bounded labor; it does not
invent roadmap, widen scope, accept its own work, or describe partial evidence as completion.

Order is mandatory:

```text
Preserve current verified repair
  -> deploy exact reviewed commit to Render staging
  -> prove Render -> outbound Mac worker task execution
  -> implement strict checkpoint lineage and recovery
  -> prove one external client-project delivery loop
  -> run one low-risk AlphaBrain self-development task
```

Meeting/Eva, AgentLine calls, client portal, and production deployment remain deferred until this
kernel passes.

## 2. Current verified baseline

Current local base before this pack:

- Git baseline commit: `7c1a463`.
- Working tree intentionally contains uncommitted senior repair. Never reset, stash, discard,
  checkout over, or clean it.
- Full suite: `480 passed`.
- Ruff, Ruff format, mypy across 56 source files, and `git diff --check`: passing.
- Hermetic spool proof: encrypted event at rest, acknowledgement-driven replay, one persisted
  attempt.
- Hermetic crash proof: real `TaskEngine.timeout_expired_leases`, retry release, one persisted
  attempt, zero duplicate results.
- Render staging task admission now requires registered project and immutable repository binding.
- Control plane validates path syntax/root binding only. Mac worker validates real directory and
  Git worktree.
- Progress watchdog uses latest authenticated heartbeat, PostgreSQL row locking, retry/escalation,
  and worker-side cancellation after lease revocation.
- Production launchd worker was running as PID `78202` during verification. PID is observational,
  not a stable identifier; re-read launchd state before every live packet.

Current intended changed files:

```text
TODO.md
alpha_core/api/app.py
alpha_core/config.py
alpha_core/state/task_engine.py
alpha_worker/daemon.py
testscript/conftest.py
testscript/test_api_and_workflow.py
testscript/test_config_and_logging.py
testscript/test_control_plane.py
testscript/test_control_plane_p4.py
testscript/test_state_engine.py
testscript/resilience_harness.py
docs/implementation/AGY_POST_D3_4_EXECUTION_PACK.md
```

Any additional changed file is a scope conflict until explained.

## 3. Target architecture

```text
Founder-approved ProjectRegistration
  -> Render control plane stores immutable project -> Mac repo reference
  -> Founder submits frozen TaskEnvelope + digest + gates
  -> Supabase persists task, approval, lease, events, attempts, evidence
  -> outbound launchd Mac worker authenticates with short-lived identity
  -> worker leases task over HTTPS
  -> worker validates local repo root, Git state, base commit, allowed paths
  -> AGY executes in isolated worktree and project-bound conversation
  -> worker heartbeats progress/checkpoints
  -> watchdog revokes stale lease and worker cancels local process
  -> worker submits typed result or encrypted spool event
  -> control plane verifies lease, packet, paths, gates, idempotency
  -> supervisor independently reruns gates
  -> founder accepts, rejects, or queues refinement
```

### 3.1 Authority boundaries

| Component | Owns | Must never own |
|---|---|---|
| Render control plane | task truth, approvals, leases, events, evidence metadata | Mac filesystem access, AGY execution |
| Supabase staging | durable state, migration revision, audit history | secrets, raw OAuth tokens, local paths as executable authority |
| Mac worker | filesystem/Git validation, worktree, AGY process, local encrypted spool | task acceptance, production approval |
| AGY | bounded code edits and declared tests | roadmap, approval, deployment, scope expansion |
| Senior supervisor | packet design, review, acceptance decision | fabricated proof |
| Founder | remote side-effect approval and final acceptance | implicit approval through chat prose |

### 3.2 Truth rules

- Process exit, model message, file change, preview URL, or health response alone is not success.
- Every accepted task requires task-linked diff, declared gate output, clean scope, and independent
  verification.
- `blocked` is correct when safety boundary stops execution.
- Local proxy/SQLite proof must be labeled hermetic local proof. It cannot be called Render,
  Supabase, staging, or production proof.
- Real staging proof requires Render API state, Supabase state, Mac worker logs/state, and final
  task/attempt evidence for same task ID.

## 4. Global AGY execution contract

Every packet must obey:

1. Read this document completely before action.
2. Print current branch, HEAD, `git status --short`, and exact packet allowlist.
3. Do not create plans outside this frozen design. Return at most five lines of orientation.
4. Use `code-review-graph` before edits and after edits when available. Disclose absence.
5. Never reset, stash, clean, force checkout, delete user work, install dependencies, or rewrite
   unrelated files.
6. Test scripts belong only under `testscript/`; evidence belongs only under
   `testscript/evidence/`; operational docs belong under `docs/`.
7. Every shell command must have a preceding comment describing its purpose.
8. Use one packet branch and one bounded commit only after every gate passes.
9. Never push, merge, deploy, migrate, alter Keychain, kill production worker, or mutate remote
   services without packet-specific founder approval.
10. Never expose secrets in output, evidence, process list, Git diff, logs, or prompt.
11. If a gate fails: diagnose, make one narrow repair inside allowlist, rerun focused gate, then
    full gates. Maximum three repair cycles. After third failure, stop `blocked` with evidence.
12. Success output must include commit SHA, changed files, exact command results, remaining risks,
    and statement of remote mutations performed or not performed.

## 5. Model routing

| Task | Model | Constraint |
|---|---|---|
| State engine, auth, checkpoint schema, migrations, worker lifecycle | Gemini 3.1 Pro High | Default coding model |
| Mechanical tests, docs reconciliation, formatting | Gemini 3.7 Flash High | No architecture decisions |
| Final independent diff review | Claude Sonnet 4.6 | Read-only; no edits |
| Architecture conflict unresolved by frozen design | Claude Opus 4.6 Thinking | Maximum one read-only turn; never full coding |

Do not silently fall back. Record selected model and reason. Quota exhaustion becomes `blocked` or
declared fallback, not hidden account rotation. Use existing safe account router and OS lock; never
edit OAuth token files or Antigravity internal databases.

## 6. Packet sequence

| Packet | Goal | Remote mutation |
|---|---|---|
| H0 | Preserve and commit current senior repair | None |
| H1 | Independent review of exact repair commit | None |
| H2 | Merge and deploy exact commit to Render staging | Founder approval required |
| H3 | Real Render-to-Mac vertical task proof | Founder task approval required |
| H4 | Real outage/crash recovery proof | Founder fault-injection approval required |
| C1 | Durable checkpoint schema and migration | Local/disposable only |
| C2 | Checkpoint API, lease lineage, resume contract | None |
| C3 | Worker checkpoint producer/resumer | None |
| C4 | Disposable PostgreSQL restart/recovery proof | Local Docker only |
| A1 | One external autonomous client-project proof | Founder task approval required |
| S1 | One low-risk AlphaBrain self-development proof | Founder task approval required |

Never skip failed packet.

---

## 7. PACKET H0 — Preserve Current Senior Repair

### Goal

Move current dirty working tree onto dedicated branch, independently verify exact current scope,
and create one local commit. No new feature work.

### Branch

`alpha/d3-4-control-worker-hardening`

### Allowlist

Only current intended changed files listed in section 2.

### Acceptance

- No current change lost.
- No extra file modified.
- `testscript/resilience_harness.py` tracked.
- Hermetic evidence remains ignored.
- `480` or more tests pass; count may increase only through intended tests.
- Ruff, format, mypy, diff check pass.
- Harness passes and leaves no child API/proxy/test worker.
- Production launchd worker remains running and untouched.
- One local commit; no push/merge/deploy.

### Reject

- Any reset/stash/clean.
- Any modification outside allowlist.
- Any attempt to “simplify” security boundaries.
- Claiming task `blocked` in disabled-AGY harness means harness failed.

### Copy-paste prompt

```text
You are AGY junior executor supervised by a senior engineer. Work only in
/Users/ajaytiwari/Desktop/Projects/alphaBrain using Gemini 3.1 Pro High, effort high.

Read docs/implementation/AGY_POST_D3_4_EXECUTION_PACK.md completely. Execute only PACKET H0.
Current working tree contains verified senior work. Preserve every byte. Never reset, stash,
clean, checkout over, or discard it. Confirm current changed files exactly match H0 allowlist.
If branch alpha/d3-4-control-worker-hardening does not exist, create it while preserving working
tree. If it exists unexpectedly, stop blocked; do not reuse or delete it.

Run code-review-graph read-only before action. Then run exact gates:
# Verify complete Python behavior.
.venv/bin/pytest -q
# Verify lint.
.venv/bin/ruff check .
# Verify formatting without rewriting unrelated files.
.venv/bin/ruff format --check .
# Verify source typing.
.venv/bin/mypy alpha_core alpha_protocol alpha_worker
# Verify whitespace and patch integrity.
git diff --check 7c1a463..HEAD
# Run disposable real-process resilience proof.
.venv/bin/python testscript/resilience_harness.py --run
# Prove no leaked harness processes and inspect launchd worker without changing it.
ps -axo pid,ppid,command | rg '(alphabrain-resilience|resilience_harness|uvicorn alpha_core.api.app:app|alpha_worker run)' || true
launchctl print gui/$(id -u)/com.deploymate.alphabrain.worker | rg 'state =|pid =|program ='

If all gates pass and scope is exact, create one local commit:
fix(worker): harden remote admission and recovery

Do not push, merge, deploy, migrate, alter Keychain, or restart production worker. Return branch,
commit SHA, exact changed files, gate outputs, harness evidence summary, and remaining risks.
```

---

## 8. PACKET H1 — Independent Review

### Goal

Review H0 commit, no edits. Find correctness, security, concurrency, recovery, test, and deployment
issues.

### Reviewer questions

1. Can Render accept Mac path reference without filesystem access?
2. Can project repo binding change after registration?
3. Can unregistered staging/production task enter queue?
4. Can healthy heartbeat be falsely stalled?
5. Can concurrent PostgreSQL watchdogs reclaim same task?
6. Does revoked heartbeat terminate local AGY execution?
7. Does network outage preserve execution and spool result safely?
8. Does harness mutate production worker, Render, Supabase, or development DB?
9. Can secrets enter evidence or logs?
10. Are status/evidence claims truthful?

### Copy-paste prompt

```text
Review only PACKET H0 commit on branch alpha/d3-4-control-worker-hardening. Use Claude Sonnet 4.6
read-only if quota exists; otherwise Gemini 3.1 Pro High read-only and label review non-independent.
Read docs/implementation/AGY_POST_D3_4_EXECUTION_PACK.md sections 1-8. Do not edit, commit, push,
merge, deploy, install, or clean. Use code-review-graph and inspect exact H0 diff plus tests.

Answer ten reviewer questions. Findings format: severity, file:line, failure scenario, narrow fix,
required regression. Reject for any P0/P1; reject for untested P2 affecting auth, task binding,
watchdog, cancellation, spool, or process cleanup. Approve only with zero unresolved P0/P1/P2.
Return APPROVE_H0 or REJECT_H0, commit SHA, evidence, and remaining low risks.
```

---

## 9. PACKET H2 — Render Staging Deployment

### Preconditions

- H0 local commit exists.
- H1 approved exact SHA.
- Main clean after explicit merge.
- Full gates rerun on main.
- Render blueprint validates.
- Supabase remains exact revision `58b5b056d9e3`.
- Founder supplies exact approval:

```text
Approve merge of H0 commit <H0_SHA> into main and deploy that exact main commit to Render staging service alpha-brain-staging. No production deployment and no database migration.
```

### Acceptance

- GitHub contains exact reviewed SHA ancestry.
- Render deployment commit equals expected main SHA.
- `/health/live` returns 200.
- `/health/ready` returns 200 and exact migration revision.
- Unauthenticated project/task/worker requests reject.
- No schema migration, Keychain change, or production service touched.

### Copy-paste prompt

```text
Execute only PACKET H2 after verifying founder approval string exactly names H0 SHA and staging
service. Use Gemini 3.1 Pro High. Re-run full gates on clean main, merge exact H0 commit without
other changes, push only approved main commit, deploy only alpha-brain-staging, and verify Render
reports exact commit. Do not run migrations. Do not touch production.

Use commented commands. Capture sanitized evidence under testscript/evidence/. Verify live and ready
endpoints, expected Alembic revision 58b5b056d9e3, unauthenticated 401 boundaries, and Render logs
without printing secrets. Stop if deployed commit differs, readiness is 503, schema differs, or any
secret is missing. Return exact Git SHA, Render service/deploy IDs, endpoint status, log summary,
and remote mutations.
```

---

## 10. PACKET H3 — Real Render-to-Mac Task Proof

### Goal

Prove same task ID travels through Render/Supabase, leases to production launchd Mac worker,
executes in isolated fixture worktree, returns one result, and produces independently verified
evidence. No proxy or local control plane.

### Test project

- Project: `prj_d3_4_real_worker_proof`.
- Repo: `/Users/ajaytiwari/Desktop/Projects/clientProjects/fixture_repo`.
- Unique task ID generated once and reused across all evidence.
- Allowed path: one predeclared fixture file under fixture repo.
- Low risk; no deployment, dependency install, network fetch, or credential change.

### Founder approval

```text
Approve one low-risk staging task for project prj_d3_4_real_worker_proof against fixture_repo. It may edit only <ALLOWED_FILE>, run declared local gates, and use the outbound Mac worker. No deployment, migration, push, or production mutation.
```

### Required evidence

- Render project registration response.
- Supabase task row, lease worker ID, attempt count, final status.
- launchd worker status before/after.
- worker task-linked sanitized logs.
- worktree branch/base/result commits.
- exact changed file list.
- declared test output and independent rerun.
- no duplicate attempts/results.

### Copy-paste prompt

```text
Execute only PACKET H3 after exact founder task approval. Use Gemini 3.1 Pro High. This must use
https://alpha-brain-staging.onrender.com directly; no localhost, proxy, mock API, SQLite, manual SQL
status rewrite, or direct database task mutation.

Read project HEAD and ensure fixture repo is clean. Register project through POST /api/projects.
Submit one frozen low-risk TaskEnvelope through POST /api/tasks with one allowed file and explicit
gates. Observe production launchd worker outbound execution. Never kill/restart worker in H3.
Independently rerun declared gates and compare task ID across Render response, Supabase task,
worker log, attempt, evidence, and result. Reject on mismatch, extra changed file, missing gate,
duplicate attempt/result, stale deployment, or local fallback. Save sanitized evidence only under
testscript/evidence/. Do not push or deploy fixture repo.
```

---

## 11. PACKET H4 — Real Recovery Proof

### Goal

Prove real staging network loss and launchd process death recovery without duplicates.

### Separate founder approval

```text
Approve controlled D3-4 staging recovery fault injection against mac_worker_local: one bounded outbound network interruption and one worker process termination, with launchd recovery. Do not change system-wide networking, Keychain, Render, Supabase schema, or unrelated processes.
```

### Safety

- Never disable Mac system-wide network.
- Use worker-specific proxy only if worker launch configuration is restored atomically afterward.
- Record original launchd plist/config hashes before change and verify exact restoration.
- Terminate only verified worker PID belonging to launchd service.
- Never `kill -9` by name or glob.
- Stop if task is not exact approved test task.

### Acceptance

- Remote task leased before fault.
- Outage creates encrypted local spool.
- Network restoration replays once after server acknowledgement.
- Process death produces expired/revoked lease through real control-plane time/watchdog path.
- launchd restarts worker.
- checkpoint/resume or safe retry yields one final result and zero duplicate side effects.
- Original launchd configuration hash restored.

### Copy-paste prompt

```text
Execute only PACKET H4 after exact founder fault-injection approval. Use Gemini 3.1 Pro High.
Preflight exact Render deploy SHA, ready endpoint, worker launchd label, PID, executable, plist hash,
Keychain secret names without reading secret values, fixture repo cleanliness, and approved task ID.

Perform bounded worker-only outage; never alter system-wide networking. Prove encrypted spool and
acknowledgement replay. Then submit separate crash task, verify exact worker PID, terminate only
that PID, allow launchd restart and real watchdog recovery, and prove one final attempt/result with
zero duplicate side effects. Restore original config in finally even on failure. Save sanitized
task-linked evidence under testscript/evidence/. Any local mock/proxy control plane must be labeled
local and cannot satisfy H4.
```

---

## 12. PACKET C1 — Durable Checkpoint Schema

### Design

Add append-only `task_checkpoints` table. Never overload mutable task JSON.

Required fields:

- checkpoint ID and monotonic sequence;
- task ID, attempt number, worker ID;
- project ID, repo reference, immutable base commit;
- worktree path and worktree HEAD;
- AGY conversation ID and execution stage;
- lease-token SHA-256 only, never raw lease token;
- side-effect state enum: `none`, `prepared`, `started`, `committed`, `compensated`, `unknown`;
- scrubbed checkpoint JSON and canonical payload digest;
- idempotency key;
- created timestamp;
- unique `(task_id, attempt_number, sequence)` and idempotency constraints.

No remote migration in C1. Prove base→head→base→head using disposable PostgreSQL 17.

### Copy-paste prompt

```text
Execute only PACKET C1 using Gemini 3.1 Pro High. Create branch alpha/c1-durable-checkpoints.
Implement additive task_checkpoints schema, ORM model, Alembic migration, protocol model, and tests.
Store only lease token hash and scrubbed checkpoint payload. No raw token, prompt, provider payload,
or secret. Do not change current task status semantics.

Use testscript/test_checkpoint_migration.py for hermetic PostgreSQL 17 migration proof with dynamic
container name, random port, Alembic Python API, and guaranteed finally cleanup. Run focused tests,
full pytest, Ruff, format, mypy, and diff check. No Supabase migration, push, merge, or deploy.
Stop after clean local commit and return SHA plus exact migration proof.
```

---

## 13. PACKET C2 — Checkpoint API and Lease Lineage

### Design invariants

- Only authenticated lease owner may append checkpoint.
- URL/body task ID must match.
- Project, repo, base commit, worker, attempt, conversation, worktree, and side-effect state bind to
  task/lease lineage.
- Sequence must increase exactly; same idempotency key + same digest returns existing checkpoint.
- Same idempotency key + different digest rejects.
- Stale/revoked lease cannot append.
- Resume never reuses old raw lease token. New lease references validated prior checkpoint lineage.
- Recovery task leases only to compatible worker when checkpoint worktree is worker-local.
- `unknown` or `committed` side-effect state requires founder review; never automatic replay.

### APIs

```text
POST /api/tasks/{task_id}/checkpoints
GET  /api/tasks/{task_id}/checkpoints/latest
POST /api/tasks/{task_id}/resume-decision
```

### Copy-paste prompt

```text
Execute only PACKET C2 after C1 is reviewed. Use Gemini 3.1 Pro High. Implement authenticated,
append-only checkpoint APIs and lease-lineage validation exactly as frozen in section 13. No raw
lease token storage. No resume on mismatched project/repo/base/worktree/conversation/worker or
unsafe side-effect state. Add adversarial tests for stale token, stolen worker, duplicate key,
digest conflict, out-of-order sequence, subject mismatch, and unsafe side effects.

Do not implement worker changes yet. No remote mutation, push, merge, or deploy. Run focused/full
tests, Ruff, format, mypy, migration regression, and diff check. Stop after local commit.
```

---

## 14. PACKET C3 — Worker Checkpoint Producer and Resumer

### Design

Worker emits checkpoints only at stable boundaries:

1. worktree validated;
2. AGY conversation bound;
3. implementation started;
4. AGY process exited;
5. gates started/completed;
6. result prepared;
7. result acknowledged or spooled.

Checkpoint payload contains hashes/references, never source contents or secrets. Worker resumes only
same worker-local worktree and conversation when control-plane resume decision is safe. Otherwise
it creates clean retry or blocks for founder.

### Copy-paste prompt

```text
Execute only PACKET C3 after C2 review. Use Gemini 3.1 Pro High. Add checkpoint client methods and
worker stable-boundary emission. Resume only from server-issued decision tied to new lease and exact
checkpoint digest. Verify local worktree path, Git HEAD/base ancestry, project, repo, conversation,
worker, and side-effect state before resuming. Any mismatch blocks; never auto-clean worktree.

Transport outage spools checkpoint/result encrypted and replays in sequence. Add deterministic
tests for crash after each stable boundary, duplicate replay, invalid digest, different worker,
missing worktree, changed HEAD, and committed side-effect state. No remote mutation or deployment.
```

---

## 15. PACKET C4 — Recovery Proof

Use disposable PostgreSQL, local API, real worker subprocess, fixture Git repo, and stub AGY adapter
with deterministic checkpoints. Kill process after each stable boundary. Never manual-rewrite task
status. Invoke actual watchdog, retry, checkpoint, and resume APIs.

Acceptance: one logical side effect, one accepted result, correct attempt lineage, no duplicate
commit, no orphan process/container/worktree, full evidence.

### Copy-paste prompt

```text
Execute only PACKET C4 using Gemini 3.1 Pro High. Build testscript/checkpoint_recovery_harness.py.
Use disposable PostgreSQL 17, random ports, managed subprocess groups, fixture Git repo, and a
deterministic stub adapter. Inject process death after every checkpoint boundary. Do not update task
status directly in SQL. Use actual API/watchdog/retry/resume flow. Assert one logical side effect,
one accepted result, exact checkpoint lineage, and zero leaked resources. Run full gates and stop
after local evidence. No staging mutation.
```

---

## 16. PACKET A1 — External Autonomous Project Proof

After H3/H4 and C1-C4 pass, create one new directory under
`/Users/ajaytiwari/Desktop/Projects/clientProjects/`. AlphaBrain must own requirement→DAG→AGY→QA→
preview evidence. Senior/founder supplies brief; no human directly codes project.

Use small project with meaningful frontend/backend/test slice. Calculator is not reused. Suggested:
offline project-status board importing a JSON task report, filtering status, and showing evidence.

Acceptance:

- separate project directory and AGY conversation;
- frozen requirements and task DAG;
- allowed paths per task;
- tests, accessibility/browser smoke, security scan, build;
- local preview with functional browser verification;
- founder review; no production deploy.

### Copy-paste prompt

```text
Execute only PACKET A1 after founder approves frozen brief and task DAG. Use AlphaBrain APIs and
outbound Mac worker for every implementation task. Do not directly edit client project from
supervisor chat. Each AGY task receives exact allowed paths, gates, dependencies, and risk.
Use Gemini 3.1 Pro High for coding and Gemini 3.7 Flash High for mechanical QA. Produce local
preview and task-linked evidence. Do not accept project until independent browser behavior,
build, tests, lint, security, and changed-file boundaries pass. No production deployment.
```

---

## 17. PACKET S1 — AlphaBrain Self-Development Proof

Only after A1 passes. Choose one low-risk TODO item touching at most two source files plus focused
tests. AlphaBrain creates task against its own clean immutable base. Founder approves digest. AGY
implements in isolated worktree. Supervisor independently verifies and founder accepts/merges.

Forbidden first self-task areas: auth, migrations, deployment, Keychain, ActionBroker, approvals,
lease engine, checkpoint lineage, destructive operations.

### Copy-paste prompt

```text
Execute only PACKET S1 after external A1 proof is accepted. Select one low-risk AlphaBrain TODO
item outside forbidden areas, then stop and present frozen TaskEnvelope, digest, allowed files,
commands, risks, and rollback for founder approval. After approval, run through normal AlphaBrain
project/task/worker/AGY/evidence loop. AGY cannot self-approve or merge. Reject extra files, missing
evidence, dirty base, conversation mismatch, or unverified model prose. No deployment or push.
```

## 18. Supervisor acceptance template

For every packet:

```text
PACKET: <ID>
BRANCH: <branch>
COMMIT: <sha>
MODEL: <model and effort>
SCOPE: <exact files>
FOCUSED GATES: <commands and results>
FULL PYTEST: <count and result>
RUFF: <result>
FORMAT: <result>
MYPY: <result>
DIFF CHECK: <result>
LIVE/HERMETIC PROOF: <scope and result>
REMOTE MUTATIONS: <none or exact approved mutation>
SECURITY FINDINGS: <none or list>
REMAINING RISKS: <list>
DECISION: ACCEPT | REJECT | RETRY | BLOCKED
NEXT PACKET: <ID or none>
```

No packet advances without `ACCEPT` from supervisor or explicit founder approval where required.
