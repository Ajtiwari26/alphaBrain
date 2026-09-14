# AlphaBrain Next Phase Roadmap: Self-Development Pipeline

This roadmap outlines the prioritized sequence for AlphaBrain's autonomous self-development. In accordance with the strict self-development invariant, **no code is manually edited**. All tasks listed here are admitted into the AlphaBrain triage queue, and will be developed using the `research -> plan -> execute -> review -> merge` autonomous cycle.

Telephony and voice features (`alpha_meet`, `alpha_voice`, AgentLine, etc.) are explicitly excluded from this roadmap.

---

## Completed & Merged Milestones (September 2026)

### Task 1: Worker Execution Adapters
- **Status**: `[-] SUPERSEDED`
- **Resolution**: Discarded Codex dependency. Standardized on `alpha_worker/adapters/antigravity_live.py` which natively executes all tasks via Google Antigravity CLI (`agy`) and Gemini 3.1 Pro High.

### Task 2: Sandbox & Daemon Isolation
- **Status**: `[x] COMPLETED & MERGED` (`commit 6e11eeb`, `tsk_eva_47cc21ccaea2`)
- **Objective**: Isolated autonomous coding worker inside restricted non-admin macOS user environment via `launchd`.

### Task 3: Temporal Workflow Integration
- **Status**: `[x] COMPLETED & MERGED` (`commit 276d945`, `tsk_eva_29983ef163bf`)
- **Objective**: Migrated task state engine to durable Temporal workflows.

### Task 4: Tenant Isolation & Authentication
- **Status**: `[x] COMPLETED & MERGED` (`commit 773cbde`, `tsk_eva_ad11f5fe2258`)
- **Objective**: Enforce multi-tenant boundaries and RBAC with JWT token claims and scoped SQL filtering.

### Task 5: Automated Deployment Adapters
- **Status**: `[x] COMPLETED & MERGED` (`commit 24eb3af`, `tsk_eva_61135c1759ef`)
- **Objective**: Implemented deterministic Vercel and Render deployment adapters with rollback pipelines.

### Task 6: Client Portal API & Frontend
- **Status**: `[x] COMPLETED & MERGED` (`commit 5599d81`, `tsk_eva_3d9c0ffc2606`)
- **Objective**: Implemented Amazon-style client tracking portal UI (`alpha_portal/`) and FastAPI live SSE stream endpoint.

### Task 8: Parallel Worker Dispatcher Daemon
- **Status**: `[x] COMPLETED & MERGED` (`commit c859b57`, `tsk_eva_faabb0476659`)
- **Task Title**: Implement Parallel Worker Dispatcher Daemon for Concurrent Worktree Execution
- **Objective**: Query TaskTriageQueue for approved tasks and manage a concurrent pool of up to max_workers in isolated worktrees
- **Allowed Scope**: `alpha_worker/parallel_dispatcher.py`, `alpha_worker/`
- **Acceptance Criteria**: Passes multi-worker lease concurrency tests without race conditions or lock contention.

### Task 7: Autonomous TODO and Roadmap State Machine Sync Engine
- **Status**: `[x] COMPLETED & MERGED` (`commit e70bf73`, `tsk_eva_37eceb12e1b8`)
- **Task Title**: Implement Autonomous TODO and Roadmap Synchronization Engine
- **Objective**: State machine synchronization engine to automatically parse merged task metadata and update TODO.md and NEXT_PHASE_ROADMAP.md
- **Allowed Scope**: `alpha_core/automation/`, `alpha_core/triage_cli.py`
- **Acceptance Criteria**: Passing unit tests verifying markdown parsing, checklist regex update, and idempotency.

### Task 9: Async Redis Rate Limiter for FastAPI Endpoints
- **Status**: `[x] COMPLETED & MERGED` (`commit 40b5e21`, `tsk_eva_5fb3a94658b7`)
- **Task Title**: Evaluate and implement open-source Python Redis rate limiter for async FastAPI (`tsk_eva_5fb3a94658b7`)
- **Objective**: Implement async Redis and in-memory fallback token-bucket rate limiter for FastAPI endpoints
- **Allowed Scope**: `alpha_core/api/rate_limiter.py`
- **Acceptance Criteria**: Unit tests and lint gates pass cleanly.

### Implement P9.7 Operational Monitoring and Live Metrics Telemetry Exporter for AlphaBrain
- **Status**: `[x] COMPLETED & MERGED` (`commit 15b839f`, `tsk_eva_b5fa5c42cd60`)
- **Objective**: Implement P9.7 Operational Monitoring and Live Metrics Telemetry Exporter for AlphaBrain

### Integrate CIHealingDaemon with ParallelWorkerDispatcher and TaskTriageQueue
- **Status**: `[x] COMPLETED & MERGED` (`commit 6899625`, `tsk_eva_c4eb3d7b96bd`)
- **Objective**: Automated CI/CD failure analysis, repair synthesis, and parallel auto-retry loop with circuit breaker protection

### Implement macOS launchd persistent supervisor for CI/CD Self-Healing Daemon and ParallelWorkerDispatcher
- **Status**: `[x] COMPLETED & MERGED` (`commit 3f26fe9`, `tsk_eva_bf0605fe5a51`)
- **Objective**: Implement macOS launchd persistent supervisor for CI/CD Self-Healing Daemon and ParallelWorkerDispatcher

### Implement Adaptive Hardware Concurrency Manager and Gemini-Powered Pipeline Mechanic
- **Status**: `[x] COMPLETED & MERGED` (`commit f106563`, `tsk_eva_159a8263d109`)
- **Objective**: Implement Adaptive Hardware Concurrency Manager and Gemini-Powered Pipeline Mechanic

### Implement OpenAI Codex Senior Review & Planning Integration with CODEX_ON_HOLIDAY Circuit Breaker
- **Status**: `[x] COMPLETED & MERGED` (`commit 16c905a`, `tsk_eva_0aa79e3888d2`)
- **Objective**: Implement OpenAI Codex Senior Review & Planning Integration with CODEX_ON_HOLIDAY Circuit Breaker

### Fix directory prefix matching in triage_dispatcher post-gate containment
- **Status**: `[x] COMPLETED & MERGED` (`commit 079a7c8`, `tsk_eva_ef43e7472649`)
- **Objective**: Fix directory prefix matching in triage_dispatcher post-gate containment

### P13.1 Production Data Privacy, Consent Management, and Data Retention Engine
- **Status**: `[x] COMPLETED & MERGED` (`commit da25fcf`, `tsk_eva_d3e234883c78`)
- **Objective**: P13.1 Production Data Privacy, Consent Management, and Data Retention Engine

### P14: Build AlphaBrain Founder Companion mobile app with React 19 + Vite + Tailwind + Capacitor Android, implementing all 14 DeployMate Locomotive screens, FastAPI backend bridge, and compiling debug Android APK for device 10BF5P2AZF0010T
- **Status**: `[x] COMPLETED & MERGED` (`commit 4181c70`, `tsk_eva_c1b1b4ca54ca`)
- **Objective**: P14.3-PARITY: Symmetrical Full Feature Parity for Mac Desktop & Mobile Companion

### P14.2-BACKEND: Cloud-First Provisioning & Node Registry API
- **Status**: `[x] COMPLETED & MERGED` (`commit ca32697`, `tsk_eva_7775f157f872`)
- **Objective**: P14.2-BACKEND: Cloud-First Provisioning & Node Registry API

### P14.2-FRONTEND: Mobile Remote Control Screens & Pixel-Perfect Access Gate
- **Status**: `[x] COMPLETED & MERGED` (`commit 3df612e`, `tsk_eva_c1e6a3d51de2`)
- **Objective**: P14.2-FRONTEND: Mobile Remote Control Screens & Pixel-Perfect Access Gate

### P14.2-DESKTOP: Tauri 2.0 Rust Core Mac App & 4 Locomotive Screens (M-01 to M-04)
- **Status**: `[x] COMPLETED & MERGED` (`commit 57341a1`, `tsk_eva_689ad86800a2`)
- **Objective**: P14.4-DESKTOP-BUNDLE: Tauri 2.0 MacOS Application Packaging and Entrypoints

---

## Active Parallel Development Pipeline (Current)

---

## Execution Handoff

Tasks are admitted into the `alpha_core` triage queue and executed via the autonomous pipeline:
1. `alpha_core.triage_cli review <task_id>`
2. `alpha_core.triage_cli approve <task_id>`
3. `alpha_core.triage_cli senior-research <task_id>`
4. `alpha_core.triage_cli senior-plan <task_id>`
5. `alpha_core.triage_cli worker-cycle <task_id>`
6. `alpha_core.triage_cli senior-review <task_id>`
7. `alpha_core.triage_cli merge <task_id>`
