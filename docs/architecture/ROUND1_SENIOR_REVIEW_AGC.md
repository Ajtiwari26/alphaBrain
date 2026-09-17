# Round 1 Senior Architectural Audit: Context Lifecycle Management & AGC

**Reviewer:** Gemini 3.1 Pro High (Senior Staff Architect)
**Date:** 2026-09-18
**Topic:** Architectural Garbage Collector (AGC) & Context Lifecycle Management

## 1. Automated AGC vs. Structured Archival Lifecycle
AlphaBrain requires a **Structured Archival Lifecycle** managed by an automated AGC. Blindly truncating or deleting old architectural drafts, MABs, and Round 1/2 syntheses would violate Invariants I-1 through I-68 (specifically those around cryptographic provenance, audit trails, and strict closed-loop isolation). An automated AGC must act as a lifecycle policy enforcer, moving artifacts through defined states rather than just deleting them, thereby preserving the cryptographic lineage required by the P9 Constitution.

## 2. Lifecycle Tiers

### Tier A: Active Working Set
- **Contents:** The current canonical `SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`, its modular topic components (if split), active epic MABs (Multi-Agent Blueprints), and ongoing active invariants.
- **Access:** Kept in plaintext in `docs/architecture/`. Fully ingested by all subagents and Tier 0/Tier 3 agents.
- **Rule:** Strict mutation rules apply; only Claude Opus 4.6 (Thinking) is authorized to author/modify these files.

### Tier B: Cold Archival
- **Contents:** Completed, superseded, or deprecated epic MABs, and old Round 1/Round 2 reviews.
- **Location:** Moved to `docs/architecture/archive/<epic_id>/`.
- **Format:** Compressed (e.g., gzip or zstd to save token ingestion space if accidently read) and accompanied by a `manifest.json` containing SHA-256 hashes of the files prior to compression. This preserves cryptographic provenance without bloating the active context window.

### Tier C: Pruned Ephemeral Artifacts
- **Contents:** Intermediate review drafts, scratchpad outputs, temporary daemon output logs used strictly for short-term debugging during an SDLC cycle.
- **Action:** Contents are summarized and merged into Git commit trailers (e.g., `AlphaBrain-Review-Hash: <sha256>`) of the final merge commit. The raw disk files are then permanently deleted. 

## 3. Addressing the Monolithic Growth of SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md

### Modularization Strategy
The monolithic document should be split into an ultra-compact master index and modular topic files:
- `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` (Master Index & Core Invariants Summary).
- `docs/architecture/invariants/` (Detailed breakdown of I-1 through I-68).
- `docs/architecture/topologies/` (System topologies, diagrams, Eva integration rules).
- `docs/architecture/security/` (Triage pipeline, cryptographic pre-execution gates).

### Preserving Claude Opus's Exclusive Authoring Authority
1. **Instructional Guardrails:** The Master Index must explicitly state that ALL files matching the glob `docs/architecture/**/*.md` are restricted to Claude Opus 4.6 (Thinking).
2. **Safety Gate Enforcement (Layer 4 & Path Protection Engine):** Update the Path Protection Engine (Section 6.4.3) to protect the entire `("docs", "architecture")` tuple from modification by standard Worker Dispatch tasks, ensuring that only specialized SDLC Opus-driven pipelines can mutate them. 

## 4. Automation Triggers for Garbage Collection

The Architectural Garbage Collector (AGC) should be triggered deterministically to prevent drift:
1. **Post-Merge Hook:** A Git post-merge hook or a dedicated pipeline step (`.venv/bin/python -m alpha_core.triage_cli gc` or `merge-cleanup`) executes immediately after a PR merge.
2. **Phase Completion Hook:** Whenever an epic or phase transitions to `COMPLETED` in the triage queue, the AGC runs a cleanup pass to move the relevant MABs and Round 1 reviews to Tier B.
3. **Periodic Daemon Sweep:** Similar to the Worktree Garbage Collection (Section 6.3), the worker daemon should run a periodic sweep (e.g., every 24 hours) to clear out Tier C ephemeral artifacts older than 48 hours.

## 5. Round 1 Verdict

**Verdict:** **AMEND**

**Reasoning:** 
The proposed architecture provides a robust mechanism to reduce context bloat while maintaining strict cryptographic provenance. However, before approval, we must explicitly ensure the `triage_cli gc` implementation is purely deterministic and cannot accidentally flag Tier A active specs for Tier C deletion if an epic spans a long duration. 

I recommend advancing this design to Round 2. Claude Opus 4.6 (Thinking) must stress-test the state transitions between Tier A and Tier B, ensuring that no race condition exists where an active epic is prematurely archived.

