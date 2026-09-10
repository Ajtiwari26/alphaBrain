# AlphaBrain Next Phase Roadmap: Self-Development Pipeline

This roadmap outlines the prioritized sequence for AlphaBrain's autonomous self-development. In accordance with the strict self-development invariant, **no code is manually edited**. All tasks listed here are admitted into the AlphaBrain triage queue, and will be developed using the `research -> plan -> execute -> review -> merge` autonomous cycle.

Telephony and voice features (`alpha_meet`, `alpha_voice`, AgentLine, etc.) are explicitly excluded from this roadmap.

---

## Part 1: Finalize Partially Implemented Foundation (Priority 1)

These components have skeletal structures but lack production implementation.

### Task 1: Worker Execution Adapters
- **Task Title**: Implement Codex and Gemini worker adapters for autonomous execution
- **Objective**: Replace mocked worker execution in `alpha_worker/adapters` with real integrations for Antigravity, Codex, and Gemini execution workers.
- **Allowed Scope**: `alpha_worker/adapters/`
- **Acceptance Criteria**: Adapters successfully parse tasks, stream telemetry, and exit cleanly with structured result schemas.

### Task 2: Sandbox & Daemon Isolation
- **Task Title**: Harden macOS `launchd` non-admin worker isolation
- **Objective**: Finalize the `daemon.py` and `launchd` configuration to securely isolate the autonomous coding worker inside a restricted non-admin macOS user environment.
- **Allowed Scope**: `alpha_worker/daemon.py`, `alpha_worker/launchd_status.py`
- **Acceptance Criteria**: Launchd plists deploy successfully to target user; unauthorized file access is blocked by macOS permissions.

### Task 3: Temporal Workflow Integration
- **Task Title**: Migrate task state engine to Temporal workflows
- **Objective**: Replace local SQLite mutable polling with a real Temporal Cloud or local Temporal cluster workflow engine for robust, durable task progress tracking.
- **Allowed Scope**: `alpha_core/queue/`, `pyproject.toml`
- **Acceptance Criteria**: Task admittance, leasing, and completion are driven by Temporal signals and queries.

---

## Part 2: Build Untouched Core Features (Priority 2)

These features have not been started and require fresh implementation.

### Task 4: Tenant Isolation & Authentication
- **Task Title**: Implement strict Tenant Isolation and API Authentication
- **Objective**: Enforce multi-tenant boundaries and RBAC for all FastAPI routes, replacing current anonymous or single-tenant default scopes.
- **Allowed Scope**: `alpha_core/api/`, `alpha_core/database/`
- **Acceptance Criteria**: JWT-based auth enforces project-level scope; cross-project queries return 403.

### Task 5: Automated Deployment Adapters
- **Task Title**: Build Vercel/Render deployment adapters and rollback pipelines
- **Objective**: Allow AlphaBrain to autonomously deploy passed PRs to preview environments and manage production rollbacks.
- **Allowed Scope**: `alpha_core/deployments/` (New)
- **Acceptance Criteria**: Adapter can trigger a deployment, poll status, and return a public preview URL.

### Task 6: Client Portal API
- **Task Title**: Implement the Client Tracking Portal API
- **Objective**: Build endpoints for clients to track workflow phases, view preview links, and approve specifications/deployments.
- **Allowed Scope**: `alpha_portal/api/` (New)
- **Acceptance Criteria**: Endpoints expose read-only state for clients and write-access for milestone approvals.

---

## Execution Handoff

These tasks have been admitted into the `alpha_core` triage queue. 

To execute them autonomously, the operator should run the standard AlphaBrain lifecycle for each task:
1. `alpha_core.triage_cli review <task_id>`
2. `alpha_core.triage_cli approve <task_id>`
3. `alpha_core.triage_cli senior-research <task_id>`
4. `alpha_core.triage_cli senior-plan <task_id>`
5. `alpha_core.triage_cli worker-cycle <task_id>`
6. `alpha_core.triage_cli senior-review <task_id>`
7. `alpha_core.triage_cli merge <task_id>`
