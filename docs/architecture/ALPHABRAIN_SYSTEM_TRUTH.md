# AlphaBrain: Unified System Design, Architecture & Living Master Truth

> **Document Status**: Canonical Living Single Source of Truth (SSOT)  
> **Repository**: `Ajtiwari26/alphaBrain`  
> **Active Branch**: `main`  
> **Last Synchronized**: 2026-09-18 (Ratified through Invariant I-72)  
> **Authority**: Supreme Living Specification under Claude Opus 4.6 Thinking & gpt-6-astra Strategic Oversight  
> **Update Invariant**: Any architectural change, file relocation, or subsystem addition MUST update this document in the same commit.

---

## 1. Executive Purpose & Product Vision

AlphaBrain is a production-grade, fail-closed **autonomous self-developing software engineering system**. It is designed to autonomously triage, research, plan, execute, verify, review, and merge code modifications into its own repository with zero direct human code editing and zero supervisor hallucinations.

### The Core Operational Philosophy
1. **Zero Direct Manual Edits**: Humans and assistant models never touch application source code directly in the working tree. All changes are executed exclusively by autonomous workers inside isolated Git worktrees under deterministic gates.
2. **Separation of Strategic, Review, and Worker Powers**: Strategic architecture (Tier 0 Astra) is strictly quarantined from code editing; Senior review (Tier 3 Opus & Pro) is independent and cross-provider; Worker execution (Tier 1 Flash 3.8) is high-throughput and bounded.
3. **Deterministic Safety Over Model Discretion**: Python code, SafetyGates, and linters make binary pass/fail enforcement decisions without relying on fuzzy model self-assessment.

---

## 2. Quad-Tier Model Topology & Routing

AlphaBrain operates under an immutable 4-tier model hierarchy with strict invocation ordering ($0 \longrightarrow 3 \longrightarrow 1 \longrightarrow 2$):

```
[ Tier 0: gpt-6-astra ]
       │ Macro Architectural Blueprints (MAB) & Invariants (reasoning_effort: medium)
       ▼
[ Tier 3: Dual Senior Engineering Board ]
  ├── Gemini 3.1 Pro High (Round 1: Adversarial Code Audit & Tracing)
  └── Claude Opus 4.6 Thinking (Round 2: Cross-Examination, Synthesis & Directive Authoring)
       │ Implementation Blueprints & Worktree Dispatch Packets
       ▼
[ Tier 1: High-Throughput Autonomous Worker ]
  └── Gemini 3.8 Flash High (Git Worktree Code Modifications & Pytest Authoring)
       │ Isolated PR / Worktree Output Branch
       ▼
[ Tier 2: Deterministic Verification Gates ]
  ├── Pytest Test Suite (100% pass required; 0 failures tolerated)
  ├── Ruff / Flake8 Linters (0 errors tolerated)
  └── SafetyGates (Pre-execution & post-execution boundary checks)
```

### Tier Responsibilities & Boundaries

| Tier | Engine / Model | Primary Authority | Strict Prohibitions & Invariants |
|:---:|:---|:---|:---|
| **Tier 0** | `gpt-6-astra` | **Chief Strategic Architect**<br>Macro Architectural Blueprints (MAB), subsystem invariant design, cross-cutting topologies. Default reasoning: `medium`. | **Zero Code, Zero Tests, Zero PR Reviews, Zero Triage.** (Invariant I-63). Max 1 call per epic. Rolling hourly budget capped at 25% (I-64). |
| **Tier 3** | Dual Senior Board:<br>• `gemini-3.1-pro-high`<br>• `claude-opus-4-6-thinking` | **Adversarial SDLC Review & Planning**<br>2-Round cross-provider review (I-61, I-62). Translates MABs into implementation blueprints. Evaluates I-65 deadlocks. | Strictly enforces cross-provider independence (Google R1 + Anthropic R2). Cannot silently mutate Astra MABs without I-65 loop. |
| **Tier 1** | `gemini-3.8-flash-high` | **Autonomous Worktree Worker**<br>Modifies code, writes tests, and runs linters exclusively inside isolated Git worktrees (`/tmp/alphabrain_worktrees/<task_id>`). | Never touches `main` working tree directly. Operates strictly within Tier 3 approved blueprints. |
| **Tier 2** | Pytest, Ruff, SafetyGates | **Deterministic Verification**<br>Mechanical pass/fail gatekeeper. Validates path protection, token counts, and test passes. | Zero reasoning, zero discretion. Binary pass/fail enforcement. |

---

## 3. Subsystem Architecture & Codebase Map

The AlphaBrain codebase is structured into three strictly decoupled layers:

```
alphaBrain/
├── alpha_protocol/                 # Layer 1: Immutable Domain Contracts (Pydantic v2)
├── alpha_core/                     # Layer 2: Core Orchestrator & Governance Engine
├── alpha_worker/                   # Layer 3: Worker Execution & Senior Review Engine
├── docs/architecture/              # Canonical Directives, Living Truth & Cold Archives
└── testscript/                     # Clean, Reusable Pytest & Automation Test Suites
```

### Layer 1: `alpha_protocol` (Immutable Protocol Layer)
Defines all domain models and contract types using **Pydantic v2** with strict typing:
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
- `alpha_protocol.context` (ACQS):
  - `TaskContextPacketV1`: Token-bounded context packet ($T_{\text{packet}} \le 2,499$ tokens).

### Layer 2: `alpha_core` (Orchestrator & Governance Engine)
- `alpha_core.queue.triage_queue.TaskTriageQueue`:
  - Thread-safe SQLite database (`~/.alphabrain/triage.sqlite`) tracking task states with WAL mode.
  - Enforces atomic state transitions: `admit` $\rightarrow$ `review` $\rightarrow$ `approve` $\rightarrow$ `research` $\rightarrow$ `plan` $\rightarrow$ `worker` $\rightarrow$ `review` $\rightarrow$ `merge`.
- `alpha_core.gates.safety_gate`:
  - Deterministic checks blocking operations that violate repository invariants (e.g. modifying protected paths like `alphaBrain/alpha_meet/`, skipping tests, or direct manual commits).
- `alpha_core.planning.senior_planning_engine`:
  - Dispatches planning agents and synthesizes implementation blueprints.
- `alpha_core.planning.research_broker`:
  - Grounded multi-source research broker querying web, codebase graph, and documentation.
- `alpha_core.mobile_bridge.service`:
  - IPC and mobile sync bridge exposing task status to operator devices.
- `alpha_core.triage_cli`:
  - Unified CLI for all pipeline commands (`admit`, `review`, `approve`, `senior-research`, `senior-plan`, `worker-cycle`, `senior-review`, `merge`, `gc`).

### Layer 3: `alpha_worker` (Execution Runtime)
- `alpha_worker.worker_engine`:
  - Manages isolated Git worktrees: `git worktree add -b feat/<task_id> /tmp/alphabrain_worktrees/<task_id> main`.
  - Dispatches `gemini-3.8-flash-high` inside the worktree to edit code and author tests.
  - Runs local deterministic test suites before presenting for review.
- `alpha_worker.senior_review_engine`:
  - Enforces mandatory 2-Round debate: Round 1 Gemini 3.1 Pro High (`--effort high`), Round 2 Claude Opus 4.6 Thinking.
  - Evaluates diff, test output, and invariant compliance.
  - On approval, performs atomic fast-forward merge into `main`.
- `alpha_worker.code_review_graph`:
  - Extracts minimal topological context to avoid full repository scanning.

---

## 4. Key Subsystems Built in Latest Epoch

### A. Context Compactor & Quota Surveillance Subsystem (ACQS — Section 17.0)
Solves the quota burn problem where unconstrained queries to `gpt-6-astra` consumed 7% of rolling 5h quota per prompt:
1. **Context Compactor Engine (CCE)**:
   - Hard token ceiling: $T_{\text{packet}} \le 2,499$ tokens. Any packet $\ge 2,500$ tokens triggers `CONTEXT_OVERFLOW`.
   - Multi-Stage AST Pruning: Stages A through E. Inviolable preservation of `@field_validator`, `@model_validator`, and `@computed_field` method bodies.
   - Multi-tokenizer cross-compilation on fallback to Claude Opus.
2. **Quota & Telemetry Surveillance Engine (QSE)**:
   - Sliding 5-hour window tracking ($U_w(t) = \sum q_i$) and 5-minute EWMA burn velocity forecasting.
   - Pre-flight admission gate: $E_1 + R + B + G \le 0.25 L_5$ (25% hourly ceiling), $E_5 + R + B + G < 0.90 L_5$ (10% 5h reserve), $E_7 + R + B + G < 0.90 L_7$ (10% weekly reserve).
   - Zero-velocity guard: $v_{\text{forecast}} \le 0 \implies ETA = \text{None}$ (no divide-by-zero crashes).
3. **Isolated Dispatch Gateway (IDG)**:
   - Runs `codex exec` in non-git ephemeral scratch directories (`--cd /tmp/astra_isolated`, `--skip-git-repo-check`, `--ignore-rules`, `--sandbox read-only`).
   - Streaming JSONL parser with `MAX_LINE_LENGTH = 1,048,576` bytes (1 MiB) buffer overflow protection.
4. **Invariant I-65 `ARCHITECTURAL_DEADLOCK` Protocol**:
   - Max 2 addendum loops back to Astra on `low` mode before human escalation.

### B. Architectural Garbage Collector & Context Lifecycle Subsystem (AGC — Section 18.0)
Solves context window bloat and semantic drift across architectural documents:
1. **3-Tier Lifecycle State Machine**:
   - **Tier A (Active Working Set)**: Plaintext in `docs/architecture/` (Canonical master, roadmap, active service specs).
   - **Tier B (Cold Archival)**: Completed epic MABs and round reviews moved to `docs/architecture/archive/<epic_id>/`, compressed with a signed `manifest.json` holding pre-compression SHA-256 hashes.
   - **Tier C (Pruned Ephemeral)**: Scratch notes and debug logs merged into Git commit trailers (`AlphaBrain-Review-Hash: <sha256>`) and purged from disk.
2. **Zero-Data-Loss & Codebase Reference Immunity (Invariant I-69)**:
   - Automated reference scan: Any file referenced in `.py`, tests, or config is **hard-pinned and can never be moved or archived**.
3. **Maintenance CLI (Invariant I-72)**:
   - `triage_cli gc --dry-run` and `archive-epic` with exact plan digests and zero `--force` bypass.

---

## 5. Consolidated Invariants Matrix (I-1 through I-72)

All 72 ratified invariants are sealed and binding. Below is the operational summary grouped by category:

| Invariant Group | Range | Core Normative Rule |
|:---|:---:|:---|
| **Autonomous Self-Development** | **I-1 – I-15** | Zero manual edits in working tree. All changes admitted via triage queue, evaluated by SafetyGates, approved by founder, and executed in isolated Git worktrees. |
| **Worktree Isolation & Safety** | **I-16 – I-30** | Workers execute inside ephemeral `.git/worktrees/`. Test execution must be deterministic with 0 failures. Modification of immutable paths (e.g. `alpha_meet/`) causes immediate pipeline abort. |
| **Pipeline Governance & Gates** | **I-31 – I-45** | Deterministic pre-execution SafetyGates; strict Pydantic v2 schemas; atomic SQLite WAL state transitions. |
| **Code Review & Dual-Model Consensus** | **I-46 – I-62** | Mandatory 2-Round SDLC review. **Invariant I-61**: Pro R1 + Opus R2. **Invariant I-62**: Strict cross-provider review independence (Google vs Anthropic). |
| **Tier 0 Astra Governance** | **I-63 – I-65** | **I-63**: Astra strictly quarantined to MAB; barred from code, tests, PR reviews, triage. Max 1 call/epic.<br>**I-64**: Mode budgeting (`low`/`medium`/`high`) and 25% rolling hourly ceiling.<br>**I-65**: `ARCHITECTURAL_DEADLOCK` protocol (max 2 addendum loops on `low`). |
| **Context Compactor & Quota (ACQS)** | **I-66 – I-68** | **I-66**: Hard ceiling $T_{\text{packet}} \le 2,499$; AST Stage B validator body inviolability; multi-tokenizer cross-compilation.<br>**I-67**: Tri-boundary quota inequalities; $\le 60\text{s}$ telemetry freshness; zero-velocity guard.<br>**I-68**: Non-git ephemeral sandbox; 1MB JSONL stream buffer ceiling. |
| **Context Lifecycle & Archival (AGC)** | **I-69 – I-72** | **I-69**: Active work exclusion; age alone never allows disposal; code-referenced files hard-pinned.<br>**I-70**: Cold archive verification; `manifest.json` schema-v1 with SHA-256 pre-compression hashes; test restore.<br>**I-71**: Ephemeral pruning Git commit trailer provenance (`AlphaBrain-Review-Hash`).<br>**I-72**: Deterministic maintenance CLI (`gc --dry-run` default; no `--force` bypass). |

---

## 6. Living Directory & File Map

### Active Root Architecture Files (`docs/architecture/`)
```
docs/architecture/
├── ALPHABRAIN_SYSTEM_TRUTH.md              # THIS FILE — Living Master Truth & Architecture
├── SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md   # Canonical Master Directive (Sections 1.0–19.0; Invariants I-1–I-72 + INV-ETTA-11–20)
├── NEXT_PHASE_ROADMAP.md                   # Active Project Roadmap & Feature Backlog (3 code refs)
├── ALPHABRAIN_MOBILE_SCREENS.md            # Mobile Bridge UI Specification (2 code refs)
├── autonomous-project-kernel.md            # Kernel Process Spec (2 code refs)
├── self-development-control-loop.md        # Autonomous Loop Spec (2 code refs)
├── agy-junior-execution-contract.md        # Master Plan Execution Spec (1 code ref)
├── agy-model-account-routing-audit.md      # Model Account Routing Spec (2 code refs)
└── archive/                                # Cold Storage with Cryptographic Manifests
    ├── 2026-Q3-acqs/                       # Archived ACQS MAB, R1 review, R2 synthesis + manifest.json
    ├── 2026-Q3-agc/                        # Archived AGC MAB, R1 review, R2 synthesis + manifest.json
    ├── audits/                             # Archived historical audits + manifest.json
    └── screens/                            # Archived large HTML screen mocks + manifest.json
```

---

## 7. Operational Tooling & Account Switchers

### Account Management Tools

| Switcher CLI | Managed Targets | Primary Command | Quota Logic |
|:---|:---|:---|:---|
| **`agy-switch`** | Google AI Pro accounts (CLI `~/.gemini/`, macOS Keychain, Antigravity IDE `state.vscdb`) | `agy-switch plan`<br>`agy-switch use <email>` | Tiered OC-EDS Utility Score ($U_i$). Rotates across 8 Google Pro accounts. |
| **`codex-switch`** | OpenAI Codex CLI (`~/.codex/auth.json`, `~/.codex/config.toml`) | `codex-switch list`<br>`codex-switch use rs023229` | Manages ChatGPT Plus / Go accounts. Active: `rs023229@gmail.com` (Plus). |

---

## 8. Continuous Synchronization Protocol (Maintenance Invariant)

To ensure this document remains the **unbreakable, 100% accurate truth** as AlphaBrain continues developing:

1. **Atomic Update Mandate**: Any pull request, task merge, or architectural change that:
   - Adds or refactors a subsystem
   - Adds, modifies, or moves a file in `docs/architecture/`
   - Seals a new invariant (I-73+)
   - Changes model routing or tier boundaries  
   **MUST update `docs/architecture/ALPHABRAIN_SYSTEM_TRUTH.md` in the exact same commit.**
2. **Review Check**: Round 1 and Round 2 Senior Reviews must verify that `ALPHABRAIN_SYSTEM_TRUTH.md` matches the physical state of the repository before issuing `APPROVE` or `FINAL_APPROVAL`.
3. **Verification Command**: Run `.venv/bin/ruff check .` and `.venv/bin/pytest` after any update to guarantee 0 breakages.

---
*Authored and sealed into AlphaBrain repository on 2026-09-18.*
