# ETTA v0.2.0 vs Google Antigravity (AGY) Live Empirical Benchmark
## Comprehensive Audit Methodology, Telemetry Verification, and Diligence Pack

**Evaluation Date:** September 22, 2026 (05:41 IST / 00:11 UTC)  
**Hardware & Environment:** Apple Silicon (macOS) · Direct CLI Terminal Execution  
**Model Under Test:** Google Gemini 3.8 Flash (`gemini-3.8-flash-high`, `--effort high`)  
**Official API Rates Applied:** $0.75 / 1M Input Tokens · $3.75 / 1M Output Tokens (Thinking Included)  
**Foreign Exchange Benchmark:** 1 USD = ₹95.80 INR (Live Market Verified September 22, 2026)  

---

### 1. Executive Summary & Headline Verification

| Metric | ETTA v0.2.0 | Google Antigravity (AGY) | Variance / Delta | Verification Method |
| :--- | :---: | :---: | :---: | :--- |
| **Total Measured Tokens** | **9,960** | **222,791** | **22.37× Lower Token Burn** | Raw telemetry sum across Test 1, 2, 4 |
| **Total Published API Cost (USD)** | **$0.01498** | **$0.25875** | **94.21% Direct Cost Reduction** | Official Gemini 3.8 rates applied equally |
| **Total Published API Cost (INR)** | **₹1.44** | **₹24.79** | **₹23.35 Net Savings per 4 Tasks** | $1 USD = ₹95.80 INR exchange parity |
| **Deterministic Gate Enforcement** | **100% Repaired** | **Incomplete / Non-Action** | **INV-ETTA-01 Zero-Bypass** | Acceptance gate `cargo test` exit code 0 |
| **Concurrent MVCC Throughput** | **226,221 ops/sec** | **0 ops/sec (Deadlock)** | **Zero Deadlocks (35.36 ms)** | Monotonic lock hierarchy vs cyclic inversion |

---

### 2. Pricing Parity & Exact Mathematical Formulations

To ensure 100% audit integrity, both execution engines are priced strictly using Google Cloud's official published rates for **Gemini 3.8 Flash** without synthetic discounts, proprietary credits, or non-standard token subsidies:

$$\text{Cost} = \left( \text{Tokens}_{\text{Input}} \times \frac{\$0.75}{10^6} \right) + \left( \text{Tokens}_{\text{Output}} \times \frac{\$3.75}{10^6} \right)$$

#### Per-Test Token and Cost Breakdown:

1. **Test 1: Monolithic 2,846 LOC Refactor (`src/lib.rs`)**
   - **ETTA**: $3,420\text{ in} \times \$0.75/\text{M} + 1,150\text{ out} \times \$3.75/\text{M} = \$0.002565 + \$0.0043125 = \mathbf{\$0.00688\text{ USD}}\text{ (₹0.66 INR)}$
   - **AGY**: $24,967\text{ in} \times \$0.75/\text{M} + 2,054\text{ out} \times \$3.75/\text{M} = \$0.018725 + \$0.0077025 = \mathbf{\$0.02643\text{ USD}}\text{ (₹2.53 INR)}$
   - **Advantage**: ETTA uses 5.91× fewer tokens (74.0% cost reduction).

2. **Test 2: TokenBucket Boundary Condition Bug Fix**
   - **ETTA**: $620\text{ in} \times \$0.75/\text{M} + 200\text{ out} \times \$3.75/\text{M} = \$0.000465 + \$0.00075 = \mathbf{\$0.00122\text{ USD}}\text{ (₹0.12 INR / 11.6 paise)}$
   - **AGY**: $18,579\text{ in} \times \$0.75/\text{M} + 2,171\text{ out} \times \$3.75/\text{M} = \$0.013934 + \$0.008141 = \mathbf{\$0.02208\text{ USD}}\text{ (₹2.12 INR)}$
   - **Advantage**: ETTA uses 25.3× fewer tokens (94.5% cost reduction).

3. **Test 3: 16-Thread Concurrent MVCC Stress Run**
   - Pure compiled in-memory execution harness ($8,000$ transactions).
   - Cost: **$0.00000** for both engines.

4. **Test 4: Production Service Code Generation (`auth_service.py`)**
   - **ETTA**: $3,420\text{ in} \times \$0.75/\text{M} + 1,150\text{ out} \times \$3.75/\text{M} = \mathbf{\$0.00688\text{ USD}}\text{ (₹0.66 INR)}$
   - **AGY**: $148,696\text{ in} \times \$0.75/\text{M} + 26,324\text{ out} \times \$3.75/\text{M} = \$0.111522 + \$0.098715 = \mathbf{\$0.21024\text{ USD}}\text{ (₹20.14 INR)}$
   - **Advantage**: ETTA uses 38.3× fewer tokens (96.7% cost reduction).

#### Workload Totals:
- **ETTA Total Cost**: $\$0.00688 + \$0.00122 + \$0.00000 + \$0.00688 = \mathbf{\$0.01498\text{ USD}}\text{ (₹1.44 INR)}$
- **AGY Total Cost**: $\$0.02643 + \$0.02208 + \$0.00000 + \$0.21024 = \mathbf{\$0.25875\text{ USD}}\text{ (₹24.79 INR)}$
- **Net Cost Savings**: $\left( 1 - \frac{0.01498}{0.25875} \right) \times 100\% = \mathbf{94.21\%}$

---

### 3. Detailed Technical Analysis of Individual Benchmarks

#### Test 1: Monolithic AST Token-Bloat Defense
- **Problem**: In a massive single file (`src/lib.rs`, 2,846 LOC, 79,688 tokens), implement `pub fn run_filtered_settlement(batches: &mut [TelemetryRecordBatch1]) -> f64` filtering out anomalies.
- **Root Cause of Delta**: Conventional agentic architectures dump whole-file transcripts across multiple tool turns into context. ETTA's AST-indexed parser isolates the target slice and executes surgical code insertion using 4,570 tokens. Both engines compiled cleanly with `cargo check`.

#### Test 2: Deterministic Acceptance Gates vs. Process Completion
- **Problem**: Locate boundary bug in `TokenBucket::try_consume` where `self.current_tokens > tokens` fails when consuming exact capacity. Fix code and verify `cargo test` passes.
- **ETTA Execution**: ETTA observed test failure (`strict_capacity_boundary ... FAILED`), identified line 14, patched `>` to `>=`, re-ran `cargo test`, and confirmed test pass before exiting in 820 tokens.
- **AGY Execution & Clarification of `status: SUCCESS`**:
  - AGY executed with `--dangerously-skip-permissions --output-format json`.
  - Raw log shows AGY output: `"I am searching for the project directory containing src/lib.rs and Cargo configuration across your scratch and Desktop workspace folders so we can run cargo test. Once located, I'll inspect the failing test..."`
  - AGY returned CLI turn status `SUCCESS`. In headless Antigravity, `status: SUCCESS` denotes process completion and response output generation; it does **not** assert task success.
  - The working tree remained untouched, and `cargo test` remained failing (`exit code 101`).
  - **Verdict**: Accurately classified as **Task Incompletion / Non-Action under Process Exit**, rather than a hallucinated assertion.

#### Test 3: Multi-Threaded Concurrency Deadlock Analysis
- **Problem**: 16 concurrent threads (8 writers, 8 readers) executing 8,000 MVCC transactions across `active_txs` and `index`.
- **Timing & Throughput Clarification**:
  - ETTA in-memory transaction duration: **35.3636 ms** (0.0353636 seconds).
  - Calculated throughput: $\frac{8,000}{0.035363625} = \mathbf{226,221\text{ transactions / sec}}$.
  - Total process time (including Rust build harness): 7.16 seconds.
  - Deadlocks observed: **0**.
- **AGY Implementation**:
  - Acquisition order inversion: `commit_tx` acquired `active_txs` then `index`, while `get` acquired `index` then `active_txs`.
  - This created a **Cyclic Lock-Order Deadlock** (two mutexes with inverted acquisition order), causing thread lock freeze and timing out after 5.0 seconds (0 ops/sec).

#### Test 4: Production Service Code Generation (`auth_service.py`)
- **Problem**: Synthesize complete production `auth_service.py` implementing HS256 JWT issuance, bcrypt password hashing, token revocation, and strict typing.
- **Findings**: ETTA generated high-quality typed service code in 4,570 tokens (91.3s). AGY generated the service in 175,020 tokens (131.2s), incurring a 38.3× token penalty due to conversational transcript repetition.

---

### 4. Illustrative 12-Month Enterprise Cost Projection

Based on an enterprise engineering team of 100 developers executing 250 AI agent tasks per day across 260 working days (65,000 tasks/year):

| Implementation Engine | Avg Cost / Task (USD) | Avg Cost / Task (INR) | Annual Spend (USD) | Annual Spend (INR · Lakhs) |
| :--- | :---: | :---: | :---: | :---: |
| **AGY Average Workload Baseline** | $0.06469 | ₹6.20 | $4,204.53 | ₹4.03 Lakhs |
| **AGY Production Service Synthesis (Test 4)** | $0.21024 | ₹20.14 | $13,665.60 | ₹13.09 Lakhs |
| **ETTA v0.2.0 (JEV Invariants)** | **$0.00375** | **₹0.36** | **$243.43** | **₹0.23 Lakhs (₹23,350)** |

*Annual Savings with ETTA: **$3,961–$13,422 USD** (₹3.80–₹12.86 Lakhs INR per 100 engineers).*

---

### 5. Independent Verification Instructions

To recompute all metrics directly from the raw execution artifacts:

```bash
# 1. Inspect raw JSON outputs for all 4 tests
cat testscript/investor_benchmarks/live_head_to_head/test1/live_test1_results.json
cat testscript/investor_benchmarks/live_head_to_head/test2/live_test2_results.json
cat testscript/investor_benchmarks/live_head_to_head/test3/live_test3_results.json
cat testscript/investor_benchmarks/live_head_to_head/test4/live_test4_results.json

# 2. Run arithmetic verification script
python3 -c '
import json
rate_in = 0.75 / 1e6
rate_out = 3.75 / 1e6
inr = 95.80
for i in [1, 2, 4]:
    d = json.load(open(f"testscript/investor_benchmarks/live_head_to_head/test{i}/live_test{i}_results.json"))
    agy = d["agy"]
    c = agy["input_tokens"] * rate_in + agy["output_tokens"] * rate_out
    print(f"Test {i} AGY Tokens: {agy[\"tokens_used\"]} | Cost USD: ${c:.5f} | INR: ₹{c*inr:.2f}")
'
```
