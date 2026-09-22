# ROUND 1 SENIOR AUDIT: Etta Verification & JEV Architecture

**Auditor:** Gemini 3.1 Pro High (Senior Staff Principal Reviewer)
**Subject:** GPT-6 Astra Tier 0 Master Architectural Blueprint - Etta Verification & JEV Architecture
**Date:** September 2026

## 1. Cross-Examination of Astra's Findings

Astra's diagnosis fundamentally shifts the perspective on Etta's performance compared to AGY. I have audited the claims and find them technically sound and urgently actionable.

### A. Evaluator Defects in Decathlon Benchmark
Astra correctly identified severe flaws in the benchmark harness evaluators (LC 3013, LC 420, LC 887, LC 847, LC 10, LC 312). The benchmark was scoring Etta based on flawed expected answers. This confirms that Etta's raw reasoning capability was artificially penalized by broken test oracles, not by inherent model deficiency. The immediate remediation is to isolate the regression suite and mathematically verify the oracles.

### B. Extraction Failure on LC 887 (`super_egg_drop.pydef`)
The finding that Etta failed due to malformed artifact boundaries (`super_egg_drop.pydef super_egg_drop(...)`) rather than algorithmic failure is a critical delivery failure. Etta currently relies on fragile regex extraction and combines `stdout` and `stderr`. This validates Astra's demand for a strict separation between machine protocol and human rendering, ensuring exact delivered bytes are parsed before being tested.

### C. The LC 480 $k=1$ Empty Heap Balancing Bug
Astra diagnosed the specific crash path for LC 480 ($k=1$ removes the only element, leading to a balancing panic on empty heaps). The absence of a zero-token local execution feedback loop in Etta allowed this trivial boundary case to manifest as a total failure. If Etta possessed a bounded verification loop, this would have been caught and repaired instantly.

### D. Quadratic Token Bloat vs. Zero-Token Local Execution
Astra correctly distinguishes between LLM token consumption and local CPU execution. AGY achieves high reliability via full-history replay, incurring quadratic token bloat. Etta can achieve the same or better reliability by leveraging local Rust-supervised execution (CPU time) to verify small boundary cases and invariants, triggering token-consuming repairs *only* when hard evidence of failure exists.

---

## 2. Deconstruction into Concrete Worker Epics & Tasks

To implement Astra's Rust-native two-phase verification architecture, the following atomic, production-grade tasks are mandated for the `etta` workspace.

### Epic 1: Canonical Artifact Assembly & Protocol
**Objective:** Eliminate regex scraping; enforce typed, verifiable artifact delivery.
**Target Crates:** `etta-protocol`, `etta-cli`
**Parallelizability:** Highly Parallelizable.

*   **Task 1.1: Typed Generation Protocol**
    *   **Files:** `etta-protocol/src/artifact.rs` (new), `etta-cli/src/runner.rs`
    *   **Structs/Traits:** `ArtifactManifest { path: PathBuf, language: String, entry_point: String, content_hash: String, source: Vec<u8> }`, `DeliveryProtocol` trait.
    *   **Error Types:** `ArtifactDeliveryError::MalformedBoundary`, `ArtifactDeliveryError::HashMismatch`.
    *   **Hard Invariants:** The exact bytes delivered by the model MUST match the SHA-256 hash provided in the `ArtifactManifest`. No regex fallbacks allowed.
    *   **Acceptance Criteria:** `super_egg_drop.pydef` style emissions are explicitly rejected with `MalformedBoundary`. `etta` can cleanly parse a typed JSON/Proto stream containing the artifact.

### Epic 2: Bounded Execution Sandbox & Supervisor
**Objective:** Provide a secure, resource-constrained execution host for local Python (and other) execution.
**Target Crates:** `etta-exec-host`
**Parallelizability:** Blocked on Epic 1 for integration, but core sandbox logic can be built in parallel.

*   **Task 2.1: Resource-Constrained Subprocess Supervisor**
    *   **Files:** `etta-exec-host/src/sandbox.rs` (new), `etta-exec-host/src/lib.rs`
    *   **Structs/Traits:** `SandboxLimits { timeout: Duration, max_memory_bytes: u64, max_output_bytes: u64 }`, `IsolatedRunner` trait, `ExecutionEvidence { stdout: Vec<u8>, stderr: Vec<u8>, exit_code: i32, usage: ResourceUsage }`.
    *   **Error Types:** `SandboxError::MemoryLimitExceeded`, `SandboxError::Timeout`.
    *   **Hard Invariants:** Process must be strictly bound by wall-clock limits and maximum output bytes to prevent infinite loops and fork bombs from stalling Etta.
    *   **Acceptance Criteria:** A generated Python script containing `while True: pass` is forcefully killed after `timeout`, yielding `SandboxError::Timeout`.

### Epic 3: Local Verification & Test Planner
**Objective:** Implement the small-case oracle and property testing phase.
**Target Crates:** `etta-test-harness`, `etta-cli`
**Parallelizability:** Parallelizable alongside Epic 2.

*   **Task 3.1: Boundary & Oracle Test Generator**
    *   **Files:** `etta-test-harness/src/planner.rs` (new), `etta-cli/src/verifier.rs` (new)
    *   **Structs/Traits:** `TestPlan { boundary_cases: Vec<TestCase>, properties: Vec<PropertyCheck> }`, `OracleVerifier` trait.
    *   **Error Types:** `VerificationError::OracleMismatch { expected: String, actual: String, input: String }`.
    *   **Hard Invariants:** "100% passed" is only asserted if `TestPlan` executes successfully within `etta-exec-host` sandbox and matches oracle outputs.
    *   **Acceptance Criteria:** LC 480 with $k=1$ automatically triggers an `OracleMismatch` when tested against the trusted small-input oracle.

### Epic 4: Bounded Repair & Adaptive JEV Governor
**Objective:** Integrate local execution feedback into the JEV router to allocate repair budgets efficiently without token bloat.
**Target Crates:** `etta-policy`, `etta-cli`
**Parallelizability:** Sequentially blocked on Epic 3 (requires Verification results).

*   **Task 4.1: JEV Repair Governor**
    *   **Files:** `etta-policy/src/governor.rs` (new), `etta-cli/src/policy.rs`
    *   **Structs/Traits:** `RepairContext { artifact_hash: String, failures: Vec<VerificationError> }`, `RepairDecision { action: RepairAction, allowed_budget: u32 }`.
    *   **Error Types:** `RepairError::BudgetExhausted`, `RepairError::StalePatch`.
    *   **Hard Invariants:** A repair cannot declare its own success; it MUST be re-verified by the `OracleVerifier`. Total tokens consumed during repair MUST strictly adhere to `BudgetConservationAccountant`.
    *   **Acceptance Criteria:** If a syntax error is detected, JEV allocates exactly one repair cycle. If the repair fails, it halts with `RepairError::BudgetExhausted` rather than looping infinitely.

---

## 3. Formal Verdict & Amendments

**Verdict: AMEND**

Astra's Tier 0 Blueprint is brilliant but requires specific systemic amendments before implementation by autonomous workers. I am issuing the following amendments for Claude Opus 4.6 Thinking to synthesize in Round 2.

**Amendment 1: Strictly Enforce Zero-Context Shrinking**
Astra mentions "Compact feedback". We must mandate that *only* the specific failing input, the expected output, and the exact exception trace (truncated to `max_output_bytes`) are fed back into the repair prompt. The LLM must not receive the entire transcript history. This is the only way to mathematically guarantee Etta avoids AGY's quadratic token bloat.

**Amendment 2: Sandbox Portability Constraint**
While Wasm/Wasmtime is discussed by Astra, the immediate need is Python execution for the Decathlon benchmark. The `etta-exec-host` must implement the `SandboxLimits` using cross-platform Rust native process controls (e.g., `std::process::Command` with strictly polled timeouts and `cgroups`/Job Objects where applicable) before attempting Wasm compilation of arbitrary LLM-generated Python.

**Amendment 3: Telemetry Verification Gates**
Astra's proposed Phase 1 and Phase 2 architectures must explicitly thread the `GovernorTelemetryEmitter` to prove compliance with `INV-ETTA-27` and `INV-ETTA-25`. The Phase 2 Local Verification must emit telemetry indicating `verification_success` or `repair_initiated`, ensuring AlphaBrain can measure the exact latency overhead of local execution versus remote inference.

***End of Round 1 Audit***
