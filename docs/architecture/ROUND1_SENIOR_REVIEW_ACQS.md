# Senior Engineering Review: Round 1 — ACQS Subsystem
**Document:** ROUND1_SENIOR_REVIEW_ACQS
**Reviewer:** Gemini 3.1 Pro High (Tier 0 Senior Staff Architect for AlphaBrain)
**Subject:** MAB-ACQS-001 (Context Compactor & Quota Surveillance Subsystem)
**Date:** 2026-09-17

## 1. Executive Summary & Verdict
**Verdict:** **AMEND**

The Macro Architectural Blueprint (MAB-ACQS-001) provided by Astra is highly rigorous, logically sound, and tightly adheres to the AlphaBrain invariants (I-63, I-64, I-65). The mathematical models for quota surveillance and the strict isolation boundaries are exceptionally well-defined. 

However, to ensure bulletproof implementation by Tier 1 workers, specific amendments are required regarding AST pruning safety, zero-velocity handling in forecasting, and model-specific recompaction during fallback events.

## 2. Comprehensive Technical Feasibility Audit

### 2.1 Context Compactor Engine (CCE) & AST Pruning
- **Feasibility:** Python 3.14 `ast` module fully supports the described multi-stage pruning.
- **Risk Identified (Stage B):** The instruction to "Replace function bodies with signatures and proven behavioral constraints" is practically ambiguous for automated AST pruning. Statically determining which side-effects affect boundaries versus pure implementation is non-trivial.
- **Amendment Required:** For Pydantic v2 models, the CCE must preserve the entire AST of `@field_validator`, `@model_validator`, and `@computed_field` methods. Pruning should be restricted to standard methods and standalone functions where the signature alone is a sufficient behavioral contract.
- **Tokenizer Compatibility:** Section 2.4 specifies target-compatible tokenizers. When a fallback to `claude-opus-4-6-thinking` occurs, the token count will change. CCE must expose a `recompact(target_model)` interface.

### 2.2 Quota Surveillance Engine (QSE) Mathematical Model
- **Sliding Window & Admission Gates:** The constraints $E_1 + R + B + G \le 0.25 L_5$, $E_5 + R + B + G < 0.90 L_5$, and $E_7 + R + B + G < 0.90 L_7$ effectively codify Invariant I-64. The inclusion of reservations ($R$) and safety margin ($G$) eliminates concurrent overbooking.
- **Risk Identified (Burn Velocity):** The ETA forecast $ETA = A / v_{\text{forecast}}$ is mathematically sound but computationally unsafe if $v_{\text{forecast}} \le 0$.
- **Amendment Required:** QSE implementation must explicitly guard against `ZeroDivisionError` when computing the ETA. If $v_{\text{forecast}} == 0$, ETA should yield a designated `INFINITY` or `None` state.

### 2.3 Isolated Dispatch Gateway (IDG) & JSONL Parser
- **CLI Shape & Sandbox:** The `codex exec` arguments (`--sandbox read-only`, `--ephemeral`, stdin piping) are highly secure. 
- **Risk Identified (Parser Vulnerability):** Incremental JSONL parsing is susceptible to Memory/OOM exhaustion if the provider emits a single unbroken sequence without newlines (e.g., malicious payload or hallucinated infinite string).
- **Amendment Required:** The IDG telemetry parser must enforce a strict `MAX_LINE_LENGTH` buffer limit and proactively abort the dispatch if the chunk size exceeds this bound.

### 2.4 Strict Compliance Verification (I-63, I-64, I-65)
- **I-63 (Tier Separation):** COMPLIANT. Astra executes strictly in a non-Git, isolated sandbox without access to write tools or the raw repository.
- **I-64 (Quota Discipline):** COMPLIANT. The 25% rolling hourly ceiling is mathematically guaranteed by the pre-flight admission gate.
- **I-65 (Bounded Escalation):** COMPLIANT. The state machine explicitly limits the loop to two `ASTRA_LOW` addendum attempts before terminating in `BLOCKED_ARCHITECTURE`.

## 3. Edge Cases & Race Conditions
1. **Model Tokenizer Fallback Race:** If an `ASTRA_LOW` request is admitted but fails with a 429, the fallback to Claude is initiated. Because Claude uses a different tokenizer, the payload might exceed the 2,499 ceiling under Claude's encoding. CCE must invalidate the packet size and re-verify against Claude's tokenizer before admitting the fallback.
2. **Atomic Ledger Contention:** The QSE sequence "begin transaction → reconcile usage → evaluate gates → reserve... → commit" requires a distributed lock or row-level locking on the `quota_scope` to prevent race conditions during high-concurrency dispatch.

## 4. Implementation Breakdown for Tier 1 Workers

To translate this MAB into production code, Tier 3 should distribute the following work packets to Tier 1:

- **Worker 1: CCE & AST Distillation**
  - Implement the Python 3.14 AST visitor for Stages A-E.
  - Implement hard-coded protection for Pydantic v2 decorators to bypass Stage B body pruning.
  - Integrate `tiktoken` (for GPT models) and the Anthropic tokenizer, exposing a `compute_compaction(model_enum)` method.
  
- **Worker 2: QSE Ledger & Math Engine**
  - Build the append-only SQLite/PostgreSQL ledger.
  - Implement the $U_w(t)$ sliding window calculation.
  - Implement the EWMA velocity function with the `ZeroDivisionError` safeguard.
  - Build the atomic `reserve_capacity()` transaction with row-level locks.

- **Worker 3: IDG & Telemetry Streamer**
  - Wrap the `codex exec` subprocess command.
  - Build the asynchronous JSONL parser with `MAX_LINE_LENGTH` buffer protection.
  - Implement the `usage_status = RESERVED_IN_FLIGHT` fallback for chunked streams.

- **Worker 4: I-65 State Machine & Orchestrator**
  - Implement the `ArchitecturalDeadlockV1` state transitions.
  - Build the atomic retry counter (max 2 attempts).
  - Wire the HTTP 429 fallback promotion logic to switch models and trigger CCE recompaction.
