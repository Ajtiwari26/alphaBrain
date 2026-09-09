# AlphaBrain

AlphaBrain is DeployMate's supervised autonomous software-delivery control plane. It turns an
approved requirement into bounded engineering work, sends that work to headless AI workers,
collects executable evidence, requires independent review, and promotes only verified results.

Its purpose is not to replace founder judgment. Its purpose is to give solo founders and small
teams an affordable, continuously available engineering system without sacrificing approval,
audit, security, or recovery boundaries.

## Vision

AlphaBrain connects four DeployMate systems:

- **Unifold / AlphaMeet** captures client conversations and requirements with Eva.
- **AlphaBrain** converts approved requirements into specifications, task graphs, policies,
  approvals, evidence, and delivery state.
- **AgentLine** will provide verified progress, approval, incident, and review calls.
- **Inito** remains a local presence/privacy signal. It is not required for headless execution and
  must not keep a camera active merely to run AlphaBrain.

Target experience:

```text
client discussion
      ↓
Eva transcript and structured specification
      ↓
founder approval and deterministic safety gate
      ↓
dependency-aware task queue
      ↓
isolated Mac worktree + headless AGY execution
      ↓
tests, lint, type checks, review graph, independent review
      ↓
founder-approved promotion, preview, deployment, and progress report
```

## Who benefits

AlphaBrain is designed for:

- solo founders who need repeatable engineering delivery without immediately hiring a full team;
- small agencies managing several client repositories with consistent review and audit rules;
- low-cost startups that need local compute plus selective cloud services;
- technical leads who want AI execution but refuse unbounded repository access or unverifiable
  completion claims;
- clients who need truthful project progress, blockers, evidence, and preview links.

Expected impact: shorter requirement-to-preview time, fewer coordination gaps, lower routine
engineering cost, recoverable 24/7 work, and an evidence trail showing what changed and why.

## Current verified state

Snapshot: **9 September 2026**, local `main` commit
`ee96772bc486072fd039d8889315b4f64e897eea`.

| Area | State | Verified boundary |
|---|---|---|
| Core control plane and security | Built | Authenticated APIs, typed tasks/gates, leases, approvals, audit records, checkpoints, recovery, promotion boundaries |
| Background Mac worker | Built and tested | Outbound control-plane client, `launchd`, pause/resume, encrypted spool, crash/lease recovery, isolated worktrees |
| AlphaMeet and Eva | Built as current consumer slice | LiveKit meeting UI, Eva participant, Gemini 2.5 native-audio path, transcript/spec producer; production multi-network and privacy proofs remain |
| Self-development closed loop | **P9.1–P9.6 complete** | Triage, five-layer safety gate, HITL CLI/API, worktree dispatch, review/merge engine, dependency DAG |
| Self-development telemetry | Pending | P9.7 operational monitoring and telemetry |
| Automated CI/CD self-healing | Built | P10 |
| Cross-project federation | Future | P11 |
| AgentLine verified calls | Not complete | Call only from durable verified facts; real end-to-end approval/refinement loop remains |
| Inito integration | Not complete | Optional presence/privacy integration remains; no camera dependency for worker operation |
| Founder/client portal | Built | Role-aware event/progress APIs exist and portal UI is operational |
| Production deployment automation | Stubbed / Not complete | Staging exists; adapters are incomplete stubs and production rollback is unimplemented |

Current local quality evidence:

- `pytest -q`: **836 passed, 11 skipped**.
- `ruff check .`: passed.
- `mypy alpha_core alpha_protocol alpha_worker`: passed.
- `ruff format --check .`: passed.

Current staging health, verified 4 September 2026:

- `https://alpha-brain-staging.onrender.com/health/live` → HTTP 200.
- `https://alpha-brain-staging.onrender.com/health/ready` → HTTP 200.

Local `main` is currently ahead of `origin/main`; staging health does not prove staging code parity
with every local commit.

## What autonomous self-development now proves

Initial H5 evidence proved only a bounded one-line `TODO.md` promotion. Current system has since
completed complex code tasks through its triage pipeline, including:

- `tsk_eva_f9be4de99e4b`: audit-export CLI implementation;
- `tsk_eva_bbf9a76143fd`: dependency-aware task DAG, cycle detection, SQLite `json_each` leasing,
  CLI support, tests, repair rounds, and senior approval.

Second task's durable result records a completed queue state, passing full test and lint gates,
Gemini Pro review, Claude Opus final approval, and result commit matching current local `main`.

This proves **bounded supervised self-development**, not unrestricted autonomy. AlphaBrain can
write and repair production code when given an approved packet, limited paths, executable gates,
isolated worktree, independent review, and promotion authority. It must not invent business scope,
bypass approvals, fabricate evidence, push, deploy, or mutate production by itself.

## Architecture

### Control plane

`alpha_core` owns authenticated project/task APIs, durable state, policy, safety checks, approvals,
audit events, reporting, meeting services, Eva intake, and triage.

Important API surfaces include:

- health and readiness;
- project, specification, task-graph, task, approval, and promotion routes;
- worker identity, health, lease, heartbeat, result, checkpoint, and resume routes;
- project progress and role-scrubbed event history;
- triage review, approve, reject, modify, emergency-stop, lease, and result routes;
- AlphaMeet, Eva, Gemini Live, and telephony routes.

Development uses SQLite. Staging/production control-plane durability uses PostgreSQL; Supabase is
supported. Redis is not required by current code.

### Triage and safety

Eva, operators, and future federated producers cannot send work directly to a worker. Requests enter
triage, receive deterministic validation, and remain invisible to workers until approved.

Core boundaries:

- protected paths and explicit `allowed_paths`;
- typed command/gate allowlists;
- maximum file/line blast radius;
- bounded execution time, retries, queue depth, and daily work;
- dependency-cycle rejection and dependency-aware leasing;
- emergency-stop tombstone;
- immutable provenance and audit export;
- fail-closed gate-evidence integrity;
- separate executor and reviewer identities.

### Mac worker

`alpha_worker` runs outbound-only. It polls approved work, creates a task-specific Git worktree,
invokes AGY headlessly, runs acceptance gates, spools encrypted results during outages, and reports
evidence to control plane. It does not need Antigravity IDE or a browser window open.

Worker state survives network loss and process restarts. Promotion remains separate from execution.
Production secrets belong in macOS Keychain service `com.deploymate.alphabrain`, never Git or
`.env.local`.

### Model roles

Model routing is cost- and task-aware:

- Claude Opus Thinking: scarce architecture, threat analysis, and final high-risk review;
- Gemini 3.1 Pro High: implementation planning, complex repair, and mid-level engineering;
- Gemini Flash High: bounded execution, mechanical tests, documentation, and evidence collection.

Model availability changes. Safety policy, typed gates, independent review, and evidence—not model
name—decide acceptance.

### AlphaMeet and Eva

AlphaMeet provides LiveKit microphone, camera, screen share, chat, reconnect, invite, and transcript
flows. Eva joins as an AI participant and uses Gemini Live native audio. Current supported developer
model is `gemini-2.5-flash-native-audio-latest`; incompatible Gemini Live variants must not be
silently substituted.

Meeting functionality is not yet equivalent to production Google Meet. TURN/TLS, consent,
retention, deletion, recording, remote-device media, concurrent-room, and client privacy proofs
remain mandatory.

## Repository layout

```text
alpha_core/       control plane, state, policy, queue, Eva, workflows, API
alpha_protocol/   versioned contracts shared across systems
alpha_worker/     outbound Mac worker, AGY adapter, review and promotion logic
alpha_meet/       meeting frontend and room integration
alpha_voice/      voice utilities
docs/             architecture, implementation, and operations references
ops/              launchd and operational scripts
supabase/         database configuration and migrations
testscript/       all tests, smoke tools, harnesses, and sanitized evidence
```

Client projects must live outside AlphaBrain, under a dedicated projects root. AlphaBrain stores
project/repository pointers and creates isolated worktrees; it must never develop a client product
inside its own source tree.

## Local setup

Requirements: macOS or Linux, Python 3.11+, Git, and optional Docker for PostgreSQL migration tests.
LiveKit Server is required for local meeting work.

```bash
# Create isolated runtime and install project/test dependencies.
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Copy environment template; replace placeholders locally and never commit secrets.
cp .env.example .env.local

# Start local control plane and meeting site.
./.venv/bin/uvicorn alpha_core.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/meet` for local AlphaMeet.

For local LiveKit on macOS:

```bash
# Install local LiveKit server.
brew install livekit

# Start LiveKit using credentials matching .env.local.
livekit-server --bind 127.0.0.1 --node-ip 127.0.0.1 --keys $'YOUR_KEY: YOUR_32_BYTE_SECRET\n'
```

## Triage operations

Package installs `alphabrain-triage` CLI.

```bash
# Admit bounded work for safety review.
./.venv/bin/alphabrain-triage admit "Add bounded feature" \
  --allowed-paths alpha_core/example.py,testscript/test_example.py \
  --criteria "focused tests pass,full suite passes"

# Review queue and inspect task evidence.
./.venv/bin/alphabrain-triage list --json
./.venv/bin/alphabrain-triage show TASK_ID --json
./.venv/bin/alphabrain-triage review TASK_ID --json

# Approve only after reviewing immutable task content and safety verdict.
./.venv/bin/alphabrain-triage approve TASK_ID --notes "Founder approved bounded execution"

# Run one worker cycle, then require senior review before merge.
./.venv/bin/alphabrain-triage worker-cycle --json
./.venv/bin/alphabrain-triage senior-review TASK_ID --json

# Inspect dependency graph and export durable audit evidence.
./.venv/bin/alphabrain-triage dag --json
./.venv/bin/alphabrain-triage export-audit TASK_ID --output testscript/evidence/audit.json

# Stop all new autonomous intake immediately.
./.venv/bin/alphabrain-triage emergency-stop --reason operator_requested --json
```

Never use review-skip or permission-bypass options in unattended or production execution.

## Mac worker operations

Configure `WORKER_CONTROL_PLANE_URL`, `WORKER_ID`, repository allowlist, state directory, and
Keychain-backed secrets before running against staging.

```bash
# Store worker bootstrap token without echoing it.
./.venv/bin/python -m alpha_worker credentials worker-token

# Store encrypted-spool key without echoing it.
./.venv/bin/python -m alpha_worker credentials worker-spool-fernet-key

# Run, pause, resume, or inspect worker.
./.venv/bin/python -m alpha_worker run
./.venv/bin/python -m alpha_worker pause --reason maintenance
./.venv/bin/python -m alpha_worker resume
./.venv/bin/python -m alpha_worker status
```

Worker can operate with lid open and screen locked/off. Closed-lid operation depends on supported
macOS clamshell hardware, power, cooling, and network. Software cannot make a powered-off Mac run.

## Verification

```bash
# Run complete deterministic test suite.
./.venv/bin/pytest -q

# Run lint, formatting, and type gates independently.
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
./.venv/bin/mypy alpha_core alpha_protocol alpha_worker

# Check patch whitespace and repository state before accepting work.
git diff --check
git status --short
```

Never claim completion because code compiles, model says “done,” preview opens, or one focused test
passes. Required acceptance evidence depends on task risk and includes focused tests, full suite,
static gates, scope diff, process cleanup, durable audit lineage, and independent review.

## Deployment position

Render staging service and Supabase schema exist. `render.yaml` disables automatic deployment and
uses `/health/ready`; remote changes require explicit founder authorization. Current staging
service intentionally disables Antigravity execution. Mac worker performs development outbound
from local machine.

No production push, deployment, migration, or rollback should occur from routine task completion.
Preview first; production only after explicit founder approval and verified rollback evidence.

## Roadmap

Immediate priorities:

1. P9.7 operational monitoring, telemetry, truthful uptime/downtime, blocker, and recovery reports.
2. Reconcile legacy `TODO.md` phase names and checkboxes with canonical roadmap.
3. Repair current Ruff formatting drift and keep all quality gates green.
4. Prove production-grade AlphaMeet consent, privacy, TURN/TLS, remote-device, and concurrent-room
   behavior.
5. Convert Eva transcript/spec output into founder-approved delivery packets end to end.
6. Build founder/client portal over role-aware progress and event APIs.
7. Connect AgentLine calls only to verified incidents, approvals, previews, and review requests.
8. Add preview-first deployment, rollback, CI/CD self-healing, backups, and restore drills.
9. Add cross-project federation only after one-repository autonomy stays reliable under pilots.

Canonical architectural rules live in
[`docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`](docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md).
`TODO.md` still contains useful detailed acceptance checks but currently mixes legacy phase names
with newer roadmap numbering; do not calculate whole-product completion from its checkboxes until
that reconciliation is complete.

## Project status in one sentence

AlphaBrain now has a working, evidence-backed, supervised self-development spine and live staging
control plane; it is not yet a finished autonomous software company, client portal, production
meeting platform, or zero-touch deployment system.
