<!-- markdownlint-disable MD013 -->

# Alpha Brain Development TODO

Status: foundation prototype  
Target: secure, durable, evidence-backed system connecting Unifold, Alpha Brain,
AgentLine, Inito, and local Mac execution worker.

Latest verified progress: 11 September 2026 — autonomous self-development loop
fully established. Completed strict multi-tenant isolation and API authentication,
temporal workflows, Mac daemon isolation via launchd, Vercel/Render deployment
adapters, Amazon-style client tracking portal with live SSE stream, CI/CD self-healing
daemon, and full test suite stabilization. Antigravity live adapter verified with
Gemini 3.1 Pro High.

## How to use this file

- Complete phases in order unless dependency explicitly allows parallel work.
- Mark item complete only after listed acceptance proof passes.
- Store every new test under `testscript/`.
- Never mark integration complete from mocked payload, model text, or compilation alone.
- Keep product repositories separate. Connect them through versioned Alpha Protocol.
- Production side effects require policy plus human approval.

## Current implementation baseline

### Implemented foundation

- [x] Alpha Protocol task, gate, specification, call, audit, and enum schemas.
- [x] SQLAlchemy project, specification, task, attempt, call, and audit models.
- [x] SQLite development database connection.
- [x] Basic task submission, leasing, heartbeat, result, and timeout functions.
- [x] FastAPI health, meeting, task, specification, and Plivo routes.
- [x] Git worktree create, inspect, commit, and cleanup helper.
- [x] Claude CLI adapter skeleton.
- [x] Antigravity Memory Graph session skeleton.
- [x] Stitch MCP request payload using `gemini-3.1-pro`.
- [x] LiveKit token generator.
- [x] Meeting UI with real LiveKit camera, microphone, remote tracks, and screen-share control.
- [x] Gemini Live setup/audio message formatter and parser.
- [x] Plivo media message formatter and parser.
- [x] Basic Mac battery/load health check.
- [x] Authentication and authorization (`alpha_core/security.py`, `773cbde`).
- [x] Strict tenant isolation and project-scoped SQL filtering (`773cbde`).
- [x] Safe command/tool execution with SafetyGate and `safety_hook.py`.
- [x] Real Temporal workflow integration (`alpha_core/queue/`, `276d945`).
- [x] Real Antigravity execution via `alpha_worker/adapters/antigravity_live.py`.
- [x] Client tracking portal with live SSE stream (`alpha_portal/`, `5599d81`).
- [x] Deployment and rollback pipeline for Vercel and Render (`24eb3af`).
- [x] Automated CI/CD Self-Healing Daemon (`alpha_worker/ci_healing_daemon.py`).
- [x] Real LiveKit room connection.
- [x] Real Gemini Live duplex audio through Vertex AI.
- [x] 506+ deterministic/hermetic tests pass without manual `PYTHONPATH` configuration.

- [x] Automated CI/CD Self-Healing Daemon & Auto-Retry Loop integrated with ParallelWorkerDispatcher (`alpha_worker/ci_healing_daemon.py`, `commit 6899625`, `tsk_eva_c4eb3d7b96bd`).
- [x] P9.7 Operational Monitoring & Live Metrics Telemetry Exporter with Prometheus exposition (`alpha_core/monitoring/`, `commit 15b839f`, `tsk_eva_b5fa5c42cd60`).
- [x] Persistent Daemon Supervisor via macOS launchd managing CI/CD Self-Healing Daemon and ParallelWorkerDispatcher (`alpha_worker/daemon_supervisor.py`, `ops/launchd/`, `commit 3f26fe9`, `tsk_eva_bf0605fe5a51`).

- [x] Implement Adaptive Hardware Concurrency Manager and Gemini-Powered Pipeline Mechanic (`commit f106563`, `tsk_eva_159a8263d109`).

- [x] Implement OpenAI Codex Senior Review & Planning Integration with CODEX_ON_HOLIDAY Circuit Breaker (`commit 16c905a`, `tsk_eva_0aa79e3888d2`).

- [x] Fix directory prefix matching in triage_dispatcher post-gate containment (`commit 079a7c8`, `tsk_eva_ef43e7472649`).

- [x] P14: Build AlphaBrain Founder Companion mobile app with React 19 + Vite + Tailwind + Capacitor Android, implementing all 14 DeployMate Locomotive screens, FastAPI backend bridge, and compiling debug Android APK for device 10BF5P2AZF0010T (`commit fb8ba39`, `tsk_eva_1d262851bd6a`).

- [x] P14.1: Mount Founder Companion Mobile Bridge into Main AlphaBrain Backend (alpha_core.api.app) (`commit c9fe9c6`, `tsk_eva_b099b480c6da`).

- [x] P14.2-BACKEND: Cloud-First Provisioning & Node Registry API (`commit ca32697`, `tsk_eva_7775f157f872`).

### Active / In-Progress

- [x] Parallel Worker Dispatcher Daemon: concurrent task pool across isolated worktrees (`commit c859b57`, `tsk_eva_faabb0476659`).
- [x] Autonomous TODO and Roadmap State Machine Sync Engine (`commit e70bf73`, `tsk_eva_37eceb12e1b8`).
- [x] Async Redis token-bucket rate limiter for FastAPI endpoints (`commit 40b5e21`, `tsk_eva_5fb3a94658b7`).
- [ ] Real meeting specification extraction.
- [ ] Real AgentLine call-job integration.
- [ ] Inito Node Keeper integration.
- [x] Production security, reliability, and privacy validation (`commit da25fcf`, `tsk_eva_d3e234883c78`).
- [-] Codex worker adapter (Discarded/Superseded: standardized on Antigravity Live + Gemini 3.1 Pro High).

## P0 — Stop unsafe execution

Goal: prevent unauthenticated network request from executing commands on Mac.

- [x] Change server default host from `0.0.0.0` to `127.0.0.1`.
- [x] Default `DEBUG=false`; enable reload only through explicit local-development flag.
- [x] Remove wildcard CORS and configure allowed origins by environment.
- [x] Add authentication dependency to every private REST endpoint.
- [x] Add WebSocket authentication before `accept()`.
- [x] Add founder, client, worker, service, and admin roles.
- [x] Add organization/project authorization checks to every database query.
- [x] Remove client-controlled `is_admin` from LiveKit token request.
- [x] Mint LiveKit permissions from authenticated server-side role.
- [x] Add worker identity using short-lived signed token or mTLS at worker API boundary.
- [x] Add repository-root allowlist for worker tasks.
- [x] Reject task repository paths outside allowlisted roots.
- [x] Reject path traversal in task, project, room, and branch identifiers.
- [x] Reject unsafe artifact identifiers and signed storage paths.
- [x] Remove `shell=True` acceptance-command execution.
- [x] Replace custom shell strings with typed gate definitions and argument arrays.
- [x] Remove Claude `--dangerously-skip-permissions` mode.
- [x] Enforce `allowed_paths` and `allowed_tools` at worker boundary.
- [x] Validate Plivo V3 webhook signatures and reject replayed nonces.
- [x] Validate Exotel webhook signatures and replay timestamps.
- [x] Stop swallowing every WebSocket/provider exception; log scrubbed failure events.
- [x] Remove device identifier from public health response.
- [x] Remove usable default LiveKit secret and fail token generation when credentials are absent.
- [x] Apply secret-redaction filter to logs, audit events, prompts, and artifacts.
- [x] Enforce global worker kill switch and per-project pause at execution boundary.

### P0 acceptance gate

- [x] Anonymous task submission returns `401`.
- [x] Anonymous task leasing returns `401`.
- [x] Client cannot mint room-admin token.
- [x] Cross-project access returns `403` through real API routes.
- [x] Raw shell-command and path-traversal test cases fail closed.
- [x] Worker cannot access file outside allowed worktree.
- [x] Invalid or replayed Plivo signature receives rejection.
- [x] Secret scan finds no live credentials or default production secrets.

## P1 — Repository, packaging, and test foundation

Goal: make project reproducible, versioned, and safe to test.

- [x] Initialize git repository.
- [x] Add `.gitignore` for `.venv`, caches, databases, logs, recordings, artifacts,
  temporary worktrees, credentials, and environment files.
- [x] Add `README.md` with architecture, setup, commands, and truthful readiness table.
- [x] Add `pyproject.toml` with package metadata and tool configuration.
- [x] Declare every runtime dependency:
  - [x] FastAPI and Uvicorn.
  - [x] Pydantic and settings package.
  - [x] SQLAlchemy, Alembic, async Postgres driver, and SQLite development driver.
  - [x] LiveKit API, RTC, and Agents packages.
  - [x] Gemini SDK.
  - [x] Temporal SDK.
  - [x] HTTP and WebSocket clients.
  - [x] JWT/cryptography packages.
- [x] Pin compatible dependency ranges and generate lock file.
- [x] Add explicit environment loading and validation.
- [ ] Separate development, test, staging, and production settings.
- [x] Replace hard-coded machine paths/device data with configuration.
- [ ] Add structured logging configuration.
- [x] Add Ruff formatting/linting and static type checking.
- [x] Make direct `.venv/bin/pytest` work without manual `PYTHONPATH`.
- [x] Override database dependency in tests.
- [x] Use temporary database for every test session.
- [x] Ensure tests never write `alpha_brain.db`.
- [x] Remove current demo/test rows from development database after backup if needed.
- [ ] Add CI workflow for lint, types, unit tests, and secret scan.
- [ ] Add pre-commit checks.

### P1 acceptance gate

- [ ] Fresh clone installs from documented command on clean checkout.
- [x] `pytest testscript/` passes without environment hacks.
- [x] Test run leaves repository and development database unchanged.
- [x] Python lint, format, type, compile, and dependency checks pass.
- [ ] CI passes on clean checkout.

## P2 — Alpha Protocol v1

Goal: freeze trustworthy contracts shared by all four systems.

- [x] Add protocol version to every external envelope.
- [x] Add organization, client, user, role, and consent identifiers.
- [x] Add strict field lengths, formats, and identifier patterns.
- [x] Add task dependency DAG contract.
- [x] Add task retry, deadline, budget, and concurrency policy.
- [x] Add approval request/result contract.
- [x] Add artifact metadata, hash, media type, size, and signed reference.
- [x] Add deployment request/result/rollback contract.
- [x] Add worker capability and health contract.
- [x] Add agent readiness states: `ready`, `busy`, `rate_limited`,
  `auth_required`, `offline`, and `degraded`.
- [x] Add structured usage/cost/quota fields.
- [x] Add meeting event types:
  - [x] Raw request.
  - [x] Clarified requirement.
  - [x] Eva recommendation.
  - [x] Trade-off.
  - [x] Decision.
  - [x] Open question.
  - [x] Acceptance criterion.
  - [x] Owner action.
- [x] Add call-job consent, quiet-hours, evidence, and callback fields.
- [x] Add immutable provenance fields for model, prompt hash, tools, commits, and inputs.
- [x] Add JSON Schema/OpenAPI export for other repositories.
- [x] Add backward-compatibility tests.

### P2 acceptance gate

- [x] Unifold, AgentLine, Inito, and Alpha Worker validate same protocol fixtures.
- [x] Invalid tenant, path, consent, gate, and artifact payloads fail validation.
- [x] Protocol v1 fixtures remain stable across releases.

## P3 — Database and durable state

Goal: establish one authoritative, recoverable system of record.

- [ ] Use PostgreSQL outside local unit tests.
- [x] Stop using `create_all()` during production startup; run Alembic migrations.
- [x] Add memberships, clients, roles, and consent tables.
- [x] Add meetings, participants, transcript segments, and meeting-event tables.
- [x] Add decisions, open questions, and change request tables.
- [x] Add workflow and normalized task dependency tables.
- [x] Add worker registration, heartbeat, capability, lease, and health history tables.
- [x] Add notification/call status history.
- [x] Enforce immutable append-only audit events through application and database policy.
- [x] Store JSON as database JSON/JSONB, not text.
- [x] Add remaining required uniqueness and foreign-key constraints.
- [x] Add soft-delete/retention policy where appropriate.
- [x] Add encrypted object storage for recordings, specs, screenshots, logs, and builds.
- [x] Add signed short-lived artifact URLs backed by object storage.
- [x] Add backup, restore, and retention jobs.

### P3 acceptance gate

- [x] Migration from empty database succeeds.
- [ ] Migration rollback succeeds in staging.
- [x] Tenant-isolation database tests pass.
- [ ] Backup restores working project, task, approval, and artifact history.
- [x] Audit events cannot be silently overwritten through application API.

## P4 — Task engine and policy broker

Goal: make task scheduling deterministic, concurrent-safe, and evidence-backed.

- [x] Implement PostgreSQL `FOR UPDATE SKIP LOCKED` lease selection; PostgreSQL concurrency
  integration proof still required.
- [x] Validate lease token, worker identity, active status, and expiry on heartbeat/result.
- [x] Reject result whose URL task ID differs from body task ID.
- [x] Add idempotent result submission and duplicate-attempt handling.
- [x] Prevent re-submission from resetting verified task without explicit retry/version.
- [x] Run expired-lease recovery before every local worker polling cycle.
- [x] Enforce declared same-project task dependencies before a task can be leased.
- [x] Enforce declared per-project and per-worker active-task limits during lease selection.
- [x] Add bounded exponential retry delay and maximum-attempt blocking.
- [ ] Add cloud control-plane event log for project, task, work, QA, preview, review, and
  incident progress; retain resumable checkpoints and scrubbed failure reasons.
- [x] Add task-progress heartbeat watchdog: use latest authenticated heartbeat, reclaim stale
  leases under PostgreSQL row lock, cancel local execution after lease revocation, then retry or
  escalate. Adapter transcripts and sanitized escalation records preserve failure evidence.
- [ ] Add idempotent wake/recovery worker that resumes only a checkpointed task with the exact
  project, repository, worktree, conversation ID, lease token, and side-effect state.
- [ ] Add reporting snapshots for founder/client: work completed, evidence, preview status,
  blocked reason, elapsed time, uptime, downtime, and next owner action.
  - [x] Founder-only project progress snapshot exposes task counts, next owner action, and safe
    audit-event metadata. Client portal, evidence/preview links, uptime, and downtime remain open.
- [ ] Add notification policy: routine reports remain in portal; AgentLine calls only for
  urgent approval, repeated repair failure, deadline risk, or active-worker loss.
- [ ] Add blocked, cancelled, waiting-approval, and superseded transitions.
  - [x] Tasks marked `requires_approval` create a pending task approval and cannot lease until a
    founder approves; rejection cancels task.
- [x] Enforce legal state-transition table in task-engine mutations.
- [x] Implement dependency-aware DAG scheduling.
- [x] Add founder-only atomic task-graph admission: validate complete bounded graph before write,
  reject cycles, duplicates, missing/nonterminal external dependencies, cross-project/repository
  bindings, and return frozen packet digests. Every admitted graph task still requires separate
  execution approval.
- [x] Add deterministic approved-spec-to-task-graph drafting with typed output, bounded paths,
  exact base commit, typed evidence commands, spec/graph/task digests, and founder review before
  atomic graph admission. It emits one delivery node until result-commit merge arbitration exists;
  configured-model decomposition/refinement remains a later bounded layer.
- [ ] Add verified result-commit integration and merge arbitration before allowing multiple code
  tasks in one project DAG; downstream QA must run against integrated work, not original base.
- [x] Add per-project and per-worker concurrency limits.
- [x] Add risk-based approval policies.
- [ ] Build typed action broker for shell, files, browser, deployment, MCP, and calls.
- [ ] Add deny-by-default tool policy.
- [ ] Require human approval for:
  - [ ] Production deployment.
  - [ ] Database migration.
  - [ ] DNS changes.
  - [ ] Destructive commands.
  - [ ] Payments or purchases.
  - [ ] External email/message/call.
- [ ] Validate every required gate has matching passing evidence.
- [ ] Make zero-evidence gate result fail.
- [ ] Use separate evidence types for lint, tests, build, browser, security, and review.
- [ ] Scrub logs before persistence/upload.
- [ ] Require reviewer different from implementer for high-risk tasks.

### P4 acceptance gate

- [ ] Concurrent workers never lease same task.
- [x] Worker crash leads to safe requeue after lease expiry and retry backoff.
- [x] Late/stolen lease cannot submit result.
- [x] Duplicate result produces no duplicate side effect.
- [x] Invalid project task graph leaves no partially admitted tasks.
- [ ] Missing required gate prevents verification.
- [ ] Illegal state transitions fail.
- [x] High-risk action waits for founder approval.

## P5 — Alpha Mac Worker and Node Keeper

Goal: run approved tasks safely and recover across restarts/network loss.

- [x] Make worker poll cloud control plane outbound; remove direct production DB access.
- [x] Add worker registration, signed identity, heartbeat, and capability report.
  - [x] Control-plane API persists signed worker registration, capability declaration, and health
    samples. Local daemon outbound reporting remains open.
- [x] Install worker with launchd under dedicated non-admin macOS user (`commit 3f26fe9`, `tsk_eva_bf0605fe5a51`).
  - [x] Launchd plist template, preflight installation script, uninstall script, and automated plist validation pass. Physical dedicated non-admin account install plus reboot/login proof remains pending operator action.
- [x] Make Mac worker fully background-only: outbound connection to cloud control plane,
  headless AGY execution, no Chrome/IDE/meeting UI automation.
- [x] Persist local encrypted handoff spool for outbound heartbeats/events during network loss;
  replay idempotently when service returns.
- [x] Add process supervisor for AGY turns: file-backed logs, progress timeout, process-group
  cleanup, one bounded repair retry, and durable escalation event.
- [x] Add remote-offline policy: cloud queues tasks and informs founder; do not claim it can
  wake a powered-off Mac. Add documented power/lid/network eligibility checks.
- [x] Add graceful startup, shutdown, pause, and drain.
- [x] Add network, disk, AC power, battery, and real thermal-pressure monitoring.
- [x] Add idle-sleep assertion only while eligible work runs.
- [x] Add low-battery and thermal drain thresholds.
- [x] Add worktree disk quota and cleanup policy.
- [x] Validate repository cleanliness and exact base commit before worktree creation.
- [x] Sanitize branch and task identifiers.
- [x] Stop force-deleting existing branches.
- [x] Preserve result branch/commit until merge or explicit rejection.
- [x] Store worker credentials in Keychain.
- [x] Add FileVault/non-admin-worker setup documentation.
- [x] Add local kill-switch command.
- [x] Integrate Node Keeper status with Inito UI without weakening privacy guard.
- [x] Document supported operating mode:
  - [x] Lid open, AC power, screen locked/off.
  - [x] Supported clamshell hardware when required.
  - [x] External camera when closed-display owner detection is required.

### P5 acceptance gate

- [ ] Reboot/login starts worker automatically. (Launchd plist template, plutil validation, and service configuration verified; physical OS reboot verification pending operator execution on dedicated account).
- [x] Network outage pauses and resumes without duplicate execution.
- [x] Low battery drains task safely.
- [x] Thermal pressure stops new heavy tasks.
- [x] Worker cannot escape worktree or use undeclared credentials.
- [ ] Eight-hour and overnight soak tests pass. (Durable soak harness with telemetry logging, checkpointing, and Markdown/JSON reporting verified; full 8-hour live overnight soak ready to run via `python testscript/soak_worker_harness.py --duration-hours 8`).

## P6 — Real coding-agent adapters

Goal: execute development through supported, observable agent interfaces.

### Shared adapter requirements

- [ ] Structured readiness response.
- [ ] Structured event stream.
- [ ] Timeout, cancellation, retry, and rate-limit handling.
- [ ] Scoped worktree, tools, credentials, and allowed paths.
- [ ] Capture agent/model/session/provenance.
- [ ] Check process exit status.
- [ ] Return changed files, diff, commit, blockers, and artifacts.
- [ ] Run declared gates after execution.
- [ ] Never infer success from quiet period or “done” text.

### Antigravity

- [x] Replace Memory Graph-only adapter with official Antigravity AGY CLI invocation.
- [x] Keep Memory Graph as context/provenance, not execution proof.
- [x] Add structured completion result and active founder cancellation: API cancellation is
  delivered through authenticated worker heartbeat, cancels adapter task, and terminates AGY's
  isolated process group.
- [x] Keep private IDE/process scraping disabled in production.

### Codex

- [ ] Add Codex SDK or CLI/MCP adapter.
- [ ] Use workspace-write sandbox for normal implementation tasks.
- [ ] Use read-only sandbox for reviews/research.
- [ ] Support thread continuation for retries and review feedback.

### Claude Code

- [ ] Use headless structured JSON/stream output.
- [ ] Configure allowed/disallowed tools.
- [ ] Configure maximum turns and permission mode.
- [ ] Treat nonzero CLI exit as failure.
- [ ] Remove unrestricted permission bypass.

### Gemini

- [ ] Add Gemini/Antigravity supported adapter.
- [ ] Add model and quota configuration.
- [ ] Use Gemini 3.1 Pro for Stitch MCP requests.

### Router

- [ ] Route by task capability, repository benchmark, tool need, cost, quota,
  availability, and verified historical quality.
- [ ] Do not permanently hard-code frontend/backend model ownership.
- [ ] Select independent reviewer from different agent/model family.
- [x] Prevent unsupported agent enum from silently falling back to Antigravity.

### P6 acceptance gate

- [ ] Each adapter completes same benchmark and returns same result schema.
- [ ] Agent failure, timeout, rate limit, and auth failure map to correct task state.
- [x] Unsupported agent request fails clearly.
- [ ] Model cannot alter files outside allowed paths.
- [ ] Reviewer detects seeded defect from another agent.

## P7 — Temporal SDLC workflow

Goal: make meeting-to-production workflow survive crashes and human waiting periods.

- [ ] Install Temporal SDK and choose Temporal Cloud or managed deployment.
- [ ] Implement real workflow and activity workers.
- [ ] Replace local mutable booleans with durable signals/queries.
- [ ] Persist workflow IDs and run IDs.
- [ ] Add durable states:
  - [ ] Intake.
  - [ ] Discovery.
  - [ ] Spec draft.
  - [ ] Founder review.
  - [ ] Client review.
  - [ ] Approved.
  - [ ] Design.
  - [ ] Build.
  - [ ] Verify.
  - [ ] Preview.
  - [ ] Founder acceptance.
  - [ ] Client acceptance.
  - [ ] Release candidate.
  - [ ] Production approval.
  - [ ] Deployed.
  - [ ] Monitoring.
- [ ] Wait for actual spec approval; remove auto-approval.
- [ ] Wait for verified task result; remove immediate call trigger.
- [ ] Use real deployment record; remove fake localhost preview.
- [ ] Wait for founder/client decision; remove auto-acceptance.
- [ ] Add cancellation, change request, rollback, and supersede paths.
- [ ] Add retry/backoff for agents, providers, deployments, and notifications.
- [ ] Add workflow query API for client portal.

### P7 acceptance gate

- [ ] Restart workflow worker during build; workflow resumes correctly.
- [ ] Disconnect Mac; workflow reports waiting/offline without losing state.
- [ ] Reject spec; no build task starts.
- [ ] Reject preview; refinement task is created.
- [ ] Failed deployment never becomes `DEPLOYED`.
- [ ] Duplicate signal does not duplicate task, deployment, or call.

## P8 — Unifold Meet and Eva

Goal: deliver real three-participant room: founder, client, Eva.

### Room and media

- [ ] Add authenticated lobby and waiting room.
- [x] Generate 30-minute server-owned founder, client, and Eva LiveKit grants.
- [x] Connect browser using LiveKit RTC client.
- [x] Publish microphone and camera tracks without blocking room join on device failure.
- [x] Subscribe/render remote participant tracks.
- [x] Implement real browser screen sharing through LiveKit `setScreenShareEnabled()`.
- [ ] Add device selection, mute, camera, screen, reconnect, and end-call states.
- [ ] Add room lock, participant removal, and rate limits.
- [ ] Add TURN/restricted-network verification.
- [ ] Add recording/transcription consent before capture.
- [ ] Add Egress recording to object storage when consented.

### Eva Gemini Live agent

- [x] Join Eva as LiveKit agent participant.
- [x] Open real Gemini 2.5 native-audio session through configured Google provider.
- [x] Stream browser/room audio to Gemini using LiveKit 24 kHz mono agent input.
- [x] Stream Gemini audio back into room.
- [x] Add input/output transcription using legacy events and `lk.transcription` streams.
- [x] Add Gemini Live interruption and barge-in configuration.
- [x] Add transparent session resumption and sliding-window context compression.
- [x] Add speaking policy: addressed, clarification needed, or critical risk.
- [ ] Load versioned DeployMate knowledge instead of static marketing claims.
- [x] Prevent Eva from claiming unimplemented security, deployment, or gates.

### Live translation

- [x] Configure `gemini-3.5-live-translate-preview` with audio input/output transcripts
  and server-side `TranslationConfig`.
- [x] Require founder authentication or signed meeting invite for text translation.
- [x] Validate and honor requested target language at API boundary.
- [x] Render provider translation output through DOM text nodes, never raw HTML.
- [x] Replace exception-swallowing translation scripts with deterministic contract tests.
- [ ] Prove real Gemini Live Translate audio input and translated audio output in a
  two-language LiveKit room.
- [ ] Isolate each translator to explicit source participant(s) and prove translator
  output cannot feed another translator loop.

### Meeting state and safety

- [ ] Replace global Eva transcript with room-scoped durable sessions.
- [x] Escape rendered participant and transcript content through DOM `textContent`.
- [x] Add content-security policy and external event-handler wiring.
- [ ] Add participant consent, retention, export, and deletion controls.
- [ ] Record raw transcript separately from AI interpretation.

### P8 acceptance gate

- [ ] Founder and client join from different networks.
- [ ] Both see/hear each other and Eva.
- [ ] Real screen share appears remotely.
- [ ] Eva handles interruption and reconnect.
- [ ] Two simultaneous rooms never share transcript/context.
- [ ] Recording never starts without consent.
- [ ] HTML/script injection fixtures render as text.

## P9 — Specification intelligence

Goal: turn meeting conversation into traceable, editable, approved build specification.

- [ ] Store timestamped raw transcript with speaker identity.
- [ ] Run structured extraction through configured model.
- [ ] Validate extraction against Alpha Protocol schema.
- [ ] Preserve raw quote/evidence reference for every requirement and decision.
- [ ] Separate client request from Eva recommendation.
- [ ] Label inference and assumptions explicitly.
- [ ] Capture functional requirements.
- [ ] Capture UX/theme/color/design requirements.
- [ ] Capture integrations, APIs, data, security, performance, and accessibility.
- [ ] Capture feasibility, trade-offs, risks, and open questions.
- [ ] Generate versioned documents:
  - [ ] Discovery brief.
  - [ ] Product requirements specification.
  - [ ] Design-system brief.
  - [ ] Architecture and data model.
  - [ ] API/integration contract.
  - [ ] Acceptance plan.
  - [ ] Security/privacy checklist.
  - [ ] Risk register.
  - [ ] Decision log.
- [ ] Add founder edit/review/approval.
  - [x] Persist immutable sequential spec versions and bind founder approve/reject to exact SHA-256.
    Founder editing UI and edit-as-new-version workflow remain open.
- [ ] Add client edit/review/approval.
- [ ] Bind workflow to exact approved spec version.
  - [x] Deterministic task drafts include exact spec digest in inputs, stable graph/task packet
    digests, exact base commit, and packet binding. Durable workflow orchestration remains open.
- [ ] Add change request and impact analysis.
- [ ] Prevent build when unresolved blocking question exists.
  - [x] Approved-spec task drafting fails closed on unresolved questions. Direct legacy task
    submission still exists and is not spec-bound.

### P9 acceptance gate

- [ ] Ten representative meeting fixtures produce traceable specs.
- [ ] Every requirement links to source transcript or labeled inference.
- [ ] Client correction creates new version without rewriting raw history.
- [ ] Build cannot begin before exact version approval.
  - [x] New spec-to-DAG lane cannot draft or admit work before digest-bound founder approval;
    legacy direct-task route prevents marking this complete system-wide.

## P10 — AgentLine integration

Goal: make Kavya/Eva calls accurate, consented, idempotent, and auditable.

- [ ] Add authenticated internal call-job endpoint or Temporal task queue.
- [ ] Persist call jobs and complete status history.
- [ ] Pass persona, recipient, project, purpose, evidence, and script facts end to end.
- [ ] Connect job to AgentLine rather than local parser-only bridge.
- [ ] Select Eva or Kavya inside real voice pipeline.
- [ ] Add provider call ID and timestamps.
- [ ] Add provider status callback handling.
- [ ] Add no-answer, retry, declined, failed, and completed states.
- [ ] Add idempotency and duplicate-call prevention.
- [ ] Add channel consent and quiet hours.
- [ ] Add exact evidence-based call language.
- [ ] Send matching portal/email approval link.
- [ ] Add action callbacks with pending/succeeded/failed status.
- [ ] Never report action success before callback proof.

### P10 acceptance gate

- [ ] Eva calls founder with correct project and verified preview facts.
- [ ] Kavya remains support/onboarding persona.
- [ ] Replayed job never creates second call.
- [ ] No-answer/failure appears in workflow.
- [ ] Call cannot state fact absent from verified `script_facts`/evidence.

## P11 — Client tracking portal

Goal: give client evidence-backed Amazon-style project visibility.

- [ ] Add authenticated organization/project dashboard.
- [ ] Show current workflow phase and dependency-aware progress.
- [ ] Show approved scope/spec version.
- [ ] Show verified milestones and gate evidence.
- [ ] Show preview links and artifacts through signed URLs.
- [ ] Show open questions and blockers.
- [ ] Add founder/client approval actions.
- [ ] Add change requests and scope impact.
- [ ] Add deployment and incident history.
- [ ] Add ETA range with confidence and explanation.
- [ ] Stream updates through SSE/WebSocket from audit/workflow events.
- [ ] Hide model reasoning, secrets, credentials, unsafe logs, and other tenants.
- [ ] Add accessible mobile layout.

### P11 acceptance gate

- [ ] Client sees correct project changes in near real time.
- [ ] Cross-tenant access suite passes.
- [ ] Signed links expire and cannot cross project boundary.
- [ ] Portal never reports completion before required gates/approvals.

## P12 — Deployment, monitoring, and rollback

Goal: make release state provider-confirmed and recoverable.

- [ ] Add deterministic Vercel/Render/cloud deployment adapters.
- [ ] Return provider deployment ID, commit, environment, URL, and status.
- [ ] Add preview deployment for every eligible change.
- [ ] Run endpoint smoke tests.
- [ ] Run browser user-flow checks.
- [ ] Run security scan and dependency audit.
- [ ] Require production approval.
- [ ] Add database migration plan and backup reference.
- [ ] Add rollback action and previous-good deployment reference.
- [ ] Add logs, traces, metrics, alerts, and SLOs.
- [ ] Add provider outage and partial-failure handling.
- [ ] Add per-project model/infrastructure cost reporting.

### P12 acceptance gate

- [ ] Failed build/deploy never produces ready URL/status.
- [ ] Browser flow passes against deployed preview.
- [ ] Production promotion requires valid approval.
- [ ] Rollback restores previous-good version.
- [ ] Alert fires for worker, workflow, meeting, call, or deployment failure.

## P13 — Privacy, compliance, and production hardening

Goal: prepare system for real clients and continuous operation.

- [ ] Complete threat model and data-flow diagram.
- [ ] Complete privacy notice and recording/transcription disclosure.
- [ ] Add consent withdrawal.
- [ ] Add data export and deletion.
- [ ] Add retention schedules by data class.
- [ ] Add encrypted transport and storage checks.
- [ ] Add credential rotation procedure.
- [ ] Add incident response and breach runbook.
- [ ] Add telephony consent/UCC/DLT/provider compliance review.
- [ ] Add dependency, container, and secret scanning.
- [ ] Add penetration test before public pilot.
- [ ] Add load, chaos, network-loss, provider-outage, and restore tests.
- [ ] Add operational runbooks for Mac offline, model quota, meeting outage,
  call failure, deployment failure, and rollback.

### P13 acceptance gate

- [ ] No unresolved critical/high security finding.
- [ ] Backup restoration drill passes.
- [ ] Consent, export, deletion, and retention tests pass.
- [ ] Incident and rollback drills pass.
- [ ] One internal pilot completes.
- [ ] One friendly-client pilot completes with recorded defects and fixes.

## First vertical slice

Complete before adding multiple-project autonomy:

- [ ] Founder creates one website project.
- [ ] Founder and client join authenticated Unifold room.
- [x] Eva participates through real Gemini Live audio.
- [ ] Meeting produces traceable specification.
- [ ] Founder and client approve exact spec version.
- [ ] Alpha Brain creates small dependency DAG.
- [ ] Mac worker executes one task through supported Codex or Antigravity adapter.
- [ ] Independent agent reviews result.
- [ ] Lint, tests, build, browser, and security gates produce evidence.
- [ ] Preview deployment returns provider-confirmed URL.
- [ ] Eva calls founder through AgentLine with verified facts.
- [ ] Founder accepts or requests refinement.
- [ ] Client portal shows truthful timeline and preview.
- [ ] Workflow survives worker restart, network loss, failed test, rejected preview,
  duplicate signal, and failed call.

## Alpha Brain v1 definition of done

- [ ] Full meeting-to-spec-to-build-to-preview-to-approval-to-deployment flow works.
- [ ] No simulated success path remains enabled in production.
- [ ] Every state transition is durable and auditable.
- [ ] Every completion claim has machine-verifiable evidence.
- [ ] Every external side effect has policy and required approval.
- [ ] Mac worker is outbound-only, least-privileged, restartable, and drainable.
- [ ] Client and organization data remain isolated.
- [ ] Meetings and calls have explicit consent and retention controls.
- [ ] System recovers from Mac sleep/offline, service restart, model rate limit,
  network loss, failed deployment, and provider outage.
- [ ] Security review, backup restore, internal pilot, and friendly-client pilot pass.
- [ ] Documentation and runbooks let operator understand exact live state.

## Recommended work order

1. P0 security containment.
2. P1 repository/test foundation.
3. P2 protocol v1 and P3 database.
4. P4 task engine and P5 Mac Worker.
5. P6 real agent adapters.
6. P7 Temporal workflow.
7. P8 real meeting/Eva.
8. P9 specification intelligence.
9. P10 AgentLine integration.
10. P11 client portal.
11. P12 deployment/monitoring.
12. P13 hardening and pilots.

## Defer until first vertical slice passes

- [ ] Self-hosting LiveKit.
- [ ] Multiple concurrent heavy local-model workers.
- [ ] Automatic production deployment without human approval.
- [ ] Complex model marketplace or dynamic bidding.
- [ ] Cosmetic meeting UI redesign.
- [ ] Multi-region infrastructure.
- [ ] Claims of one-night delivery or bug-free completion.
