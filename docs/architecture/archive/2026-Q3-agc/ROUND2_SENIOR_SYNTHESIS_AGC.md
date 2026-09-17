# Round 2 Senior Architectural Synthesis: AGC & Context Lifecycle Subsystem

**Supreme Lead Architect:** Claude Opus 4.6 Thinking  
**Date:** 2026-09-18  
**Verdict:** 🟢 **FINAL_APPROVAL**  
**Topic:** Architectural Garbage Collector (AGC) & Context Lifecycle Subsystem  
**Prior Reviews:**  
- Round 1: Gemini 3.1 Pro High — **AMEND** ([ROUND1_SENIOR_REVIEW_AGC.md](file:///Users/ajaytiwari/Desktop/projects/AlphaBrain/docs/architecture/ROUND1_SENIOR_REVIEW_AGC.md))  
- Tier 0 Blueprint: GPT-6 Astra — MAB-AGC-001 ([MAB_AGC_001_BLUEPRINT.md](file:///Users/ajaytiwari/Desktop/projects/AlphaBrain/docs/architecture/MAB_AGC_001_BLUEPRINT.md))

---

## 1. Adversarial Cross-Examination: Gemini Round 1 (AMEND)

### 1.1 Strengths Acknowledged

Gemini's Round 1 review correctly identified the three foundational requirements that AlphaBrain's context lifecycle must satisfy:

1. **Structured lifecycle over blind deletion** — Gemini rightly rejected any approach that truncates or deletes old architectural artifacts without preserving cryptographic lineage. This aligns with I-1 through I-68's provenance requirements.

2. **Three-tier taxonomy** — The Tier A (Active Working Set), Tier B (Cold Archival), Tier C (Pruned Ephemeral) categorization is architecturally sound and was correctly motivated by the need to reduce context window bloat while preserving audit trails.

3. **Modularization strategy** — The proposal to split the monolithic `SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` into a master index with modular topic files (`invariants/`, `topologies/`, `security/`) is directionally correct and necessary given the document now exceeds 4,499 lines.

4. **Deterministic triggers** — The post-merge hook, phase-completion hook, and periodic daemon sweep provide a reasonable automation surface.

### 1.2 Critical Gaps Identified Under Adversarial Examination

> [!WARNING]
> The following gaps in Gemini's Round 1 review represent architectural risks that, if left unaddressed, could compromise AGC safety. Each gap is cross-referenced against Astra's MAB-AGC-001 resolution.

**Gap G-1: Absence of Concurrency Control Specification**

Gemini's review mentions "stress-test the state transitions between Tier A and Tier B" and warns about "race conditions where an active epic is prematurely archived," but provides **zero specification** for how to prevent this. No locking protocol, no fencing tokens, no global lock ordering, no mutation broker — just a directive to "stress-test."

- **Severity:** CRITICAL
- **Astra Resolution:** MAB-AGC-001 §2.4 specifies a complete global lock ordering (`repository → epic → artifact → catalog`), monotonically increasing fencing tokens, a mutation broker pattern, and explicit prohibition of indefinite lock waits. **ADEQUATE.**

**Gap G-2: Age-Based Pruning in Tier C Contradicts Non-Inferable Disposal**

Gemini's §4.3 recommends: *"a periodic sweep to clear out Tier C ephemeral artifacts older than 48 hours."* This is age-based disposal. Age alone cannot establish pruning eligibility — an ephemeral artifact may be referenced by a long-running review cycle that happens to take >48 hours.

- **Severity:** HIGH
- **Astra Resolution:** MAB-AGC-001 AGC-07 explicitly states: *"File age, filename, extension, directory placement, or low retrieval frequency cannot independently establish pruning eligibility."* This is the correct invariant. **Gemini's age-based criterion is overruled.**

**Gap G-3: No Transaction Protocol**

Gemini proposes "move to `docs/architecture/archive/<epic_id>/`" and "compressed, accompanied by a `manifest.json` containing SHA-256 hashes" but provides no transaction protocol — no prepare/revalidate/commit/cleanup phases, no crash recovery semantics, no atomic catalog switching.

- **Severity:** HIGH
- **Astra Resolution:** MAB-AGC-001 §2.5 specifies a 7-phase transaction protocol (Plan → Prepare → Revalidate → Publish → Commit → Clean up → Finalize) with explicit crash recovery semantics at every boundary. **ADEQUATE.**

**Gap G-4: Manifest Schema Underspecified**

Gemini's manifest specification consists of: *"a `manifest.json` containing SHA-256 hashes of the files prior to compression."* This is insufficient for a production archive format. No schema version, no transaction ID, no Git provenance binding, no artifact identity, no predecessor links.

- **Severity:** MEDIUM
- **Astra Resolution:** MAB-AGC-001 §4.2 provides a complete `manifest.json` schema-v1 with 12 required top-level fields, nested `source_git`, `bundle`, and `files[]` schemas, uniqueness constraints, and explicit prohibition of self-referential hashes. **ADEQUATE and thorough.**

**Gap G-5: No CLI Safety Specification**

Gemini mentions `triage_cli gc` but provides no argument specification, no `--dry-run` default, no `--force` prohibition, no SafetyGate integration, and no exit code semantics.

- **Severity:** MEDIUM
- **Astra Resolution:** MAB-AGC-001 §5 provides complete CLI specification with `--dry-run` as default, explicit `--force` prohibition, `--expect-plan-sha256` verification, 10 SafetyGate checks, and deterministic exit codes. **ADEQUATE.**

### 1.3 Round 1 Cross-Examination Verdict

Gemini's Round 1 review was **directionally correct** but **operationally incomplete**. It identified the right problem space and proposed the right categorical solution, but left critical implementation details — concurrency control, transaction protocol, manifest schema, CLI safety — entirely unspecified. The AMEND verdict was appropriate; the gaps necessitated the Tier 0 blueprint work.

---

## 2. Adversarial Cross-Examination: Astra MAB-AGC-001

### 2.1 Strengths Acknowledged

Astra's MAB-AGC-001 is an exceptionally rigorous blueprint that addresses every gap in Gemini's Round 1 review:

1. **AGC-01 through AGC-12** are well-formulated invariants covering authority preservation, active-work exclusion, evidence-before-removal, exact identity, exclusive authorship, fail-closed semantics, non-inferred disposal, atomic visibility, immutable archives, provenance continuity, bounded coordination, and deterministic execution.

2. **The 3-tier state machine** (§2) with explicit allowed/prohibited transitions, eligibility semantics, locking contract, and 7-phase transaction protocol is production-grade.

3. **The manifest.json schema-v1** (§4.2) is comprehensive and correctly prohibits self-referential hashes, enforces path-safe identifiers, and requires pre-compression SHA-256 verification.

4. **The failure matrix** (§6.3) covers 17 distinct failure scenarios with deterministic responses, and correctly states: *"No failure path may fall back to blind deletion."*

5. **The authority boundary** is correctly delineated: *"Activation MUST remain blocked until Claude Opus verifies compatibility against the canonical invariant text and ratifies the integration."*

### 2.2 Issues Identified Under Stress-Testing

**Issue S-1: I-65 Compatibility Binding**

Astra correctly identifies that AGC must verify I-65 compatibility but defers this to Opus ratification. I-65 governs the pre-execution safety gate's deadlock prevention. The AGC's locking protocol (§2.4) introduces new lock participants into the system — if AGC's lock ordering conflicts with I-65's implicit safety gate serialization, deadlock could occur.

- **Resolution:** I verify that AGC's global lock ordering (`repository → epic → artifact → catalog`) does not conflict with I-65. The safety gate operates at the task admission level (pre-execution), while AGC operates at the post-completion lifecycle level. These are temporally disjoint: a task must reach terminal state before AGC can consider its artifacts. The lock domains are separate. **I-65 compatibility is RATIFIED.**

**Issue S-2: `ARCHIVED_COLD → PRUNED_EPHEMERAL` Prohibition**

Astra prohibits this transition, which is correct — cold archives are immutable historical records that should never be pruned. However, the rationale should be made explicit: cold archives may contain the only surviving copy of superseded architectural decisions that inform future design choices. Pruning them would destroy irreplaceable institutional memory.

- **Resolution:** Prohibition RATIFIED with explicit rationale added to canonical Section 18.0.

**Issue S-3: Modularization Self-Ratification Prohibition**

Astra states: *"AGC cannot ratify its own modularization."* This is correct — AGC is a maintenance subsystem, not an architectural authority. The modularization of `SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` requires a separate SDLC cycle with its own Round 1/Round 2 review. AGC's role is strictly limited to lifecycle transitions of already-ratified artifacts.

- **Resolution:** Acknowledged. Modularization is a future SDLC epic, not part of AGC's scope. AGC provides the infrastructure; modularization requires separate architectural ratification.

**Issue S-4: Activation Acceptance Criteria Sufficiency**

Astra's §6.4 lists 11 acceptance criteria that must be demonstrated before AGC is enabled. These are comprehensive and include crash injection, corrupt manifest handling, non-Opus caller rejection, and modularization preservation. However, two additional criteria should be added:

1. **Lock timeout cascading**: Demonstrate that a lock timeout at any level in the global ordering correctly releases all previously acquired locks in reverse order.
2. **Concurrent archive + restore**: Demonstrate that an archive operation and a restore operation targeting different epics can proceed concurrently without interference.

- **Resolution:** Added to canonical Section 18.0 acceptance criteria.

### 2.3 Astra Blueprint Cross-Examination Verdict

MAB-AGC-001 is **architecturally sound, operationally complete, and ready for canonical integration**. The four issues identified are resolvable through ratification (S-1, S-2) or additive strengthening (S-3, S-4) rather than redesign. Astra's blueprint correctly deferred canonical authority to this Round 2 synthesis.

---

## 3. Canonical Invariant Assignments

Astra's blueprint-local invariants (AGC-01 through AGC-12) are hereby mapped to canonical invariant numbers. Not all blueprint invariants warrant standalone canonical invariants — some are subsumed by existing invariants or are operational constraints rather than architectural invariants.

| Blueprint ID | Canonical Assignment | Rationale |
|:---:|:---|:---|
| AGC-01 | Subsumed by existing I-1 through I-68 provenance chain | Authority preservation is already covered across the invariant corpus |
| AGC-02 | **I-69: Active Work Exclusion & Non-Inferable Disposal** | Novel invariant; combines AGC-02 and AGC-07 |
| AGC-03 | Subsumed by I-69 + I-70 | Evidence-before-removal is enforced through the archive verification protocol |
| AGC-04 | **I-70: Cryptographic Cold Archive Verification & Pre-Compression Digests** | Novel invariant; combines AGC-04 exact identity with archive verification |
| AGC-05 | Existing I-4 (Path Protection Engine) | Opus-exclusive authoring already enforced |
| AGC-06 | **I-72: Deterministic Maintenance CLI & Fail-Closed Guards** | Novel invariant; fail-closed + deterministic execution combined |
| AGC-07 | Merged into **I-69** | Non-inferable disposal combined with active-work exclusion |
| AGC-08 | Subsumed by I-70 transaction protocol | Atomic visibility is a property of the archive transaction |
| AGC-09 | Subsumed by I-70 immutable archive contract | Part of the cold archive specification |
| AGC-10 | **I-71: Ephemeral Pruning Commit Trailer Provenance** | Novel invariant; provenance continuity for pruned artifacts |
| AGC-11 | Subsumed by I-72's fail-closed lock semantics | Bounded coordination is operational, not architectural |
| AGC-12 | Merged into **I-72** | Deterministic execution combined with fail-closed |

**Result:** Four novel canonical invariants sealed: **I-69, I-70, I-71, I-72.**

---

## 4. Definitive Architectural Synthesis

### 4.1 Three-Tier Lifecycle Topology — RATIFIED

The three-tier lifecycle state machine is ratified with the following canonical state names:

| State | Contents | Default Retrieval |
|:---|:---|:---|
| `ACTIVE_WORKING_SET` | Current governing directives, active epic MABs, in-flight reviews, registered working artifacts | Eligible for role-scoped retrieval |
| `ARCHIVED_COLD` | Immutable, compressed historical records with verified manifest and cryptographic provenance | Excluded unless explicitly requested |
| `PRUNED_EPHEMERAL` | Source removed; durable evidence reference and tombstone retained; terminal state | Excluded |

**Allowed transitions:**
- `ACTIVE_WORKING_SET → ARCHIVED_COLD` (with full precondition chain per MAB-AGC-001 §2.2)
- `ACTIVE_WORKING_SET → PRUNED_EPHEMERAL` (with ephemeral classification and evidence capture)
- `ARCHIVED_COLD → ACTIVE_WORKING_SET` (explicit reactivation with verification)

**Prohibited transitions:**
- `ARCHIVED_COLD → PRUNED_EPHEMERAL` — Cold archives are immutable institutional memory
- `PRUNED_EPHEMERAL → *` — Terminal state; reuse creates new artifact revision linked to tombstone

### 4.2 Concurrency Control — RATIFIED

Global lock ordering: `repository → epic (ascending ID) → artifact (ascending ID) → lifecycle catalog`

- Fencing tokens: monotonically increasing, validated by mutation broker
- Reference pinning: active tasks retain durable pins beyond short-lived read locks
- Lock timeout: bounded acquisition with reverse-order release on timeout
- No model/network calls while holding mutation locks

### 4.3 Master Directive Modularization — RATIFIED FOR FUTURE EPIC

Directory taxonomy ratified:
```
docs/architecture/
├── SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md   (Master Index — canonical entry point)
├── invariants/                              (I-1 through I-72 detail modules)
├── topologies/                              (System topology diagrams)
├── security/                                (Authority, path protection, locking)
├── epics/<epic_id>/                         (Active epic MABs and reviews)
└── archive/<epic_id>/<archive_id>/          (Cold archive bundles)
    ├── manifest.json
    └── payload.tar.zst
```

**Path protection scope:** All files matching `docs/architecture/**/*.md` are restricted to Claude Opus 4.6 Thinking exclusive authoring. Enforced by Path Protection Engine (§6.4.3) covering creation, modification, deletion, rename, move, symlink, and extraction operations.

**Modularization activation:** Requires a separate SDLC epic with its own Round 1/Round 2 senior review. AGC provides lifecycle infrastructure; modularization requires separate architectural ratification.

### 4.4 Cold Archive Bundle Format — RATIFIED

- **Formats:** `tar.zst` (default), `tar.gz` (compatibility)
- **Manifest:** `manifest.json` schema-v1 per MAB-AGC-001 §4.2 (12 required fields, nested schemas)
- **Pre-compression hashes:** SHA-256 of exact original bytes, no normalization
- **Verification:** 8-step protocol before source removal (per MAB-AGC-001 §4.3)
- **Immutability:** Published archive generations cannot be overwritten; corrections create new generations

### 4.5 Ephemeral Pruning — RATIFIED WITH STRENGTHENING

- **Evidence capture:** Exact ephemeral bytes or approved durable evidence record
- **Git trailer:** `AlphaBrain-Review-Hash: <sha256>` in merge commit
- **Receipt:** Maps hash to artifact identity, original path, evidence locator, transaction, and retained commit
- **Strengthening over Gemini:** Age alone (48 hours or otherwise) does NOT establish pruning eligibility. All reference checks must pass.

### 4.6 CLI Specification — RATIFIED

- `triage_cli gc` and `archive-epic` with `--dry-run` as default
- `--apply` requires `--expect-plan-sha256` and `--authorization-ref`
- Zero `--force` bypass; no recursive deletion option
- 10 SafetyGate checks re-evaluated under coordination protection at execution time
- Exit codes: 0 (success), 2 (invalid args), 3 (gate denial), 4 (lock timeout), 5 (integrity failure), 6 (interrupted/recovery)

---

## 5. Activation Acceptance Criteria — STRENGTHENED

AGC MUST remain disabled until focused tests demonstrate all of the following (augmenting MAB-AGC-001 §6.4 with items 12-13):

1. Active, queued, reviewing, and promotion-pending work cannot be archived
2. Concurrent admission and collection preserve reference safety
3. Stale workers cannot mutate protected paths
4. Crash injection at every transaction boundary preserves recoverable evidence
5. Corrupt manifests and payloads block source removal
6. Restore reproduces original pre-compression SHA-256 values
7. Non-Opus callers cannot mutate architectural Markdown (including moves/extraction)
8. Modularization preserves every ratified section and invariant
9. Pruned artifacts retain valid evidence locators and commit-trailer provenance
10. Canonical I-65 compatibility is explicitly ratified (**RATIFIED in this synthesis, §2.2/S-1**)
11. Test scripts reside under `testscript/`
12. **[ADDED]** Lock timeout at any level in the global ordering releases all previously acquired locks in reverse order
13. **[ADDED]** Concurrent archive and restore operations targeting different epics proceed without interference

---

## 6. Round 2 Definitive Verdict

### 🟢 FINAL_APPROVAL

**Reasoning:**

The AGC & Context Lifecycle Subsystem, as synthesized from Gemini's Round 1 directional analysis and Astra's MAB-AGC-001 operational blueprint, represents a **sound, complete, and production-ready architectural design** for managing AlphaBrain's growing architectural context.

**Key ratifications:**
- Three-tier lifecycle state machine with explicit transition preconditions
- Global lock ordering with fencing tokens and mutation broker pattern
- Cold archive bundle format with SHA-256 pre-compression verification
- Ephemeral pruning with commit trailer provenance (non-age-based)
- Deterministic CLI with fail-closed guards and zero `--force` bypass
- Master directive modularization taxonomy (activation deferred to future epic)

**Invariants sealed:** I-69 (Active Work Exclusion & Non-Inferable Disposal), I-70 (Cryptographic Cold Archive Verification & Pre-Compression Digests), I-71 (Ephemeral Pruning Commit Trailer Provenance), I-72 (Deterministic Maintenance CLI & Fail-Closed Guards).

**Total sealed invariants:** I-1 through I-72.

**Canonical integration:** Section 18.0 appended to `SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` with full provenance chain.

---

## 7. SDLC Provenance Chain

| Review Stage | Agent | Model ID | Verdict | Date | Artifact |
|:---|:---|:---|:---:|:---|:---|
| Tier 0 Blueprint | GPT-6 Astra | `gpt-6-astra` | PROPOSED | 2026-09-18 | `MAB_AGC_001_BLUEPRINT.md` |
| Round 1 Senior Audit | Gemini 3.1 Pro High | `gemini-3.1-pro-high` | **AMEND** | 2026-09-18 | `ROUND1_SENIOR_REVIEW_AGC.md` |
| Round 2 Senior Synthesis | Claude Opus 4.6 Thinking | `claude-opus-4-6-thinking` | **FINAL_APPROVAL** | 2026-09-18 | `ROUND2_SENIOR_SYNTHESIS_AGC.md` |

---

*Round 2 Senior Synthesis authored and sealed by Claude Opus 4.6 Thinking on 2026-09-18.*  
*This document is an immutable SDLC artifact. Any modification requires a new SDLC cycle.*
