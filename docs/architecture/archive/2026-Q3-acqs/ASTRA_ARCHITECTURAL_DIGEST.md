# AlphaBrain System Architectural Digest (For Tier 0 Strategic Architecture)

> **Audience**: Tier 0 Chief Strategic Architect (`gpt-6-astra`)  
> **Purpose**: Dense architectural specification providing complete system topology, invariant rules, and interface schemas without repository scanning overhead.  
> **Governance Authority**: Invariants I-1 through I-65 in `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.

---

## 1. System Topology & Quad-Tier Hierarchy

AlphaBrain is an autonomous, fail-closed software development and self-evolving engineering engine. It operates on a strict 4-tier separation of concerns:

```
[ Tier 0: gpt-6-astra ]
       │ Macro Architectural Blueprints (MAB) & Invariants (medium reasoning)
       ▼
[ Tier 3: Dual Senior Engineering Board ]
  ├── Gemini 3.1 Pro High (Round 1 Adversarial Audit)
  └── Claude Opus 4.6 Thinking (Round 2 Synthesis & Directive Authoring)
       │ Implementation Blueprints & Worktree Dispatch Packets
       ▼
[ Tier 1: Autonomous Worker Engine ]
  └── Gemini 3.8 Flash High (Git Worktree Code Modifications & Pytest Suite)
       │ Worktree PR / Branch Output
       ▼
[ Tier 2: Deterministic Verification Gates ]
  ├── Pytest Test Suites (0 failures allowed)
  ├── Ruff / Flake8 Linters (0 lint errors allowed)
  └── SafetyGates (deterministic invariant compliance)
```

### Tier Invariant Boundaries
- **Tier 0 (`gpt-6-astra`)**: Macro Architectural Blueprints (MAB) only. Never touches source files, tests, PR reviews, or bug triage (Invariant I-63). Max 1 call per epic.
- **Tier 3 (Dual Seniors)**: Translates MAB into actionable implementation blueprints; conducts 2-Round cross-provider adversarial code reviews (I-61, I-62); executes `ARCHITECTURAL_DEADLOCK` resolution loop (I-65).
- **Tier 1 (Worker)**: Autonomous coding agent running exclusively in isolated Git worktrees (`.git/worktrees/`). Never modifies the main branch directly.
- **Tier 2 (Gates)**: Mechanical binary gates with zero reasoning discretion.

---

## 2. Core Codebase Modules & Schemas

### A. `alpha_protocol` (Immutable Protocol Layer)
Defines all domain models and contract types using **Pydantic v2**:
- `alpha_protocol.task`:
  - `TriageTask`: ID, title, description, priority, lifecycle state (`PENDING_REVIEW`, `APPROVED`, `IN_RESEARCH`, `IN_PLANNING`, `IN_DEVELOPMENT`, `UNDER_REVIEW`, `MERGED`, `FAILED`).
  - `SafetyAssessment`: Risk score (0.0–1.0), touched file patterns, deterministic security checks.
  - `SafetyGate`: Pre-execution invariant validator.
- `alpha_protocol.planning`:
  - `PlanBlueprint`: Structured plan with goal, scope boundaries, step-by-step file edits, and verification strategy.
  - `ResearchSnapshot`: Multi-source grounded findings and dependencies.
- `alpha_protocol.review`:
  - `ReviewPacket`: Diff snapshot, automated gate results, invariant check results.
  - `ReviewVerdict`: `APPROVE`, `REQUEST_CHANGES`, `AMEND`, or `REJECT`.
  - `SeniorReviewRecord`: Round 1 (Gemini) + Round 2 (Opus) signatures and trailers.

### B. `alpha_core` (Orchestrator & Governance Engine)
- `alpha_core.queue.triage_queue.TaskTriageQueue`:
  - Thread-safe SQLite database (`~/.alphabrain/triage.sqlite`) tracking task states with WAL mode.
  - Enforces atomic state transitions (`admit` → `review` → `approve` → `research` → `plan` → `worker` → `review` → `merge`).
- `alpha_core.gates.safety_gate`:
  - Deterministic checks blocking operations that violate repository invariants (e.g. modifying protected paths like `alphaBrain/alpha_meet/`, skipping tests, or direct manual commits).
- `alpha_core.planning.senior_planning_engine`:
  - Dispatches planning agents and synthesizes implementation blueprints.
- `alpha_core.triage_cli`:
  - Standardized CLI for all pipeline commands (`admit`, `review`, `approve`, `senior-research`, `senior-plan`, `worker-cycle`, `senior-review`, `merge`).

### C. `alpha_worker` (Execution Runtime)
- `alpha_worker.worker_engine`:
  - Manages isolated Git worktrees: `git worktree add -b feat/<task_id> /tmp/alphabrain_worktrees/<task_id> main`.
  - Dispatches `gemini-3.8-flash-high` inside the worktree to edit code and author tests.
  - Runs local deterministic test suites before presenting for review.
- `alpha_worker.senior_review_engine`:
  - Enforces mandatory 2-Round debate: Round 1 Gemini 3.1 Pro High (`--effort high`), Round 2 Claude Opus 4.6 Thinking.
  - Evaluates diff, test output, and invariant compliance.
  - On approval, performs atomic fast-forward merge into `main`.

---

## 3. Key Invariants & System Constraints

1. **Strict Autonomous Self-Development (Zero Direct Manual Edits)**:
   - Human supervisors and assistant agents never manually edit code in the main working tree.
   - All changes must be dispatched through the triage pipeline and executed inside an isolated worktree by the autonomous worker.
2. **Quota-Gated Hierarchy (I-63, I-64, I-65)**:
   - `gpt-6-astra` reasoning modes:
     - `low` (~3–8k tokens, ~2–3% 5h quota): Deadlock resolution & schema validation.
     - `medium` (~15–25k tokens, ~6–8% 5h quota, **DEFAULT**): Macro Architectural Blueprints.
     - `high` (~50–90k tokens, ~15–22% 5h quota): Reserved for cryptography/zero-day threat modeling (requires `--astra-high-override`).
   - Rolling 1-hour quota ceiling: 25% max consumption.
   - Fail-closed fallback: HTTP 429 triggers promotion of Claude Opus 4.6 Thinking to interim Tier 0 with merge commit trailer audit.
3. **`ARCHITECTURAL_DEADLOCK` Protocol (I-65)**:
   - If Tier 3 finds an Astra MAB unimplementable due to repo/environment constraints, it raises `ARCHITECTURAL_DEADLOCK` with a failure trace and advisory alternative.
   - Astra resolves via a bounded `low`-effort query issuing an Architectural Addendum (AA). Max 2 loops.

---

## 4. Current Challenge & Task Requirements

### Problem Statement
The current invocation mechanism for `gpt-6-astra` via `codex exec` does not have a dedicated context compactor or live quota surveillance layer. An unoptimized query consumed 26,636 tokens (~7% of the 5-hour quota) because it scanned the repository and loaded bloated context.

### System Design Required from Tier 0
Astra is tasked with architecting the **AlphaBrain Context Compactor & Quota Surveillance Subsystem (ACQS)**:
1. **Context Compaction Engine (CCE)**:
   - How to autonomously compile task requirements + relevant `alpha_protocol` schemas + invariant subsets into an ultra-dense, token-minimal context packet (< 2,500 tokens).
2. **Quota & Telemetry Surveillance Engine (QSE)**:
   - Continuous accounting of 5-hour rolling limit and weekly quota.
   - Live consumption rate calculation (tokens per minute, burn velocity).
   - Pre-flight admission gate: blocks Astra calls if quota is insufficient or within 10% of ceiling.
   - Countdown timer to next quota refresh window.
3. **Isolated Dispatch Gateway (IDG)**:
   - How `codex exec` should be invoked in an ephemeral, isolated workspace with `--json` streaming and zero repository scanning overhead.
4. **Failure & Deadlock State Machine**:
   - Integration with Invariants I-63, I-64, and I-65.
