**MAB-ETTA-002 — Interactive Performance and Benchmark Integrity**

**Verdict: Etta’s published superiority claims are currently unsupported; several are materially misleading. Your lag complaint matches actual code.**

This goes beyond poorly chosen metrics. Production code contains benchmark-specific canned responses, fabricated usage values on failure, and success reporting after failed live calls.

That establishes unreliable measurement and reporting. It does **not** establish anyone’s intent to deceive.

Audit scope: inspected Etta checkout at `a4d93de7baaa4adc35218c73bb55393f77f191c0`, benchmark documents, scripts, runner, and AlphaBrain execution rules. No fresh live latency measurements performed. Installed binary’s correspondence to checkout remains unverified. Session filesystem is read-only; blueprint delivered here, without code changes or worker dispatch.

**1. What evidence actually shows**

| Published claim | Finding | Disposition |
|---|---|---|
| **6.08ms JEV reflex** | Available harness sends `"Mock benchmark task..."`; runner detects that phrase and returns fixed text without invoking reflex engine in that branch. | Invalid evidence for real JEV decision latency. |
| **16.09s vs 20.05s; 19.8% faster** | Arithmetic holds. Available comparison lacks repetitions, TTFT, randomized ordering, response validation, and matched effort. | Unproven comparative advantage. |
| **8.34MB peak RAM** | Available RAM harness runs `--headless --status`, not active conversational workload. | Cannot substantiate active-session footprint, especially with AGY child. |
| **1,540 vs 79,103 base tokens** | Runner hardcodes `1540` on live failure; AGY success estimates output bytes/4, minimum 120. Neither measures base prompt. | Withdraw ratio pending provider usage evidence. |
| **9ms cold launch** | Available harness measures status invocation. No demonstrated cold filesystem caches, authenticated readiness, or first-answer timing. | Label narrowly as process/status timing under documented conditions. |
| **Native streaming eliminates AGY overhead** | Primary path explicitly launches AGY and buffers its output. | Contradicted by inspected implementation. |

Critical evidence:

- [Runner benchmark shortcut](/Users/ajaytiwari/Desktop/Projects/etta/crates/etta-cli/src/runner.rs:165): matches `"Mock "`, `"mock_"`, or `"benchmark task"` and returns fixed response plus 120 tokens.
- [Failure converted into success](/Users/ajaytiwari/Desktop/Projects/etta/crates/etta-cli/src/runner.rs:173): failed dispatch becomes `"offline_fallback"`, 1,540 tokens, $0.0035; function subsequently returns `status: "success"`.
- [Benchmark gate](/Users/ajaytiwari/Desktop/Projects/etta/testscript/performance/bench_harness.sh:105): exercises shortcut; lines 134–137 warn above **100ms** and still print PASS. It does not enforce requested **15ms** limit.
- [Live comparison](/Users/ajaytiwari/Desktop/Projects/etta/testscript/performance/compare_agy_vs_etta.py:25): varies AGY effort; Etta command stays identical. Both outputs captured until completion.
- [Whitepaper](/Users/ajaytiwari/Desktop/Projects/etta/docs/benchmarks/ETTA_GLOBAL_HARNESS_BENCHMARK_2026.html:416): attributes speedup to eliminated AGY overhead, contradicting primary runner path.

Additional reproducibility failure: Markdown reproduction references `test_comprehensive_all_functionalities.py` and `performance/comprehensive_head_to_head_v2.py`; neither exists in inspected Etta test tree. Markdown and HTML also publish different headline numbers.

**Required publication action:** mark affected claims “unverified—under correction”; preserve originals and publish erratum. Existing documents cannot serve as release acceptance evidence.

**2. Where Etta is worse—and what remains unknown**

Against a streaming AGY session, Etta’s primary path structurally delays answer display until child completion. It also starts another provider process for each submitted turn. These are concrete disadvantages.

Further verified weaknesses:

- Provider failure can appear as successful completion.
- Usage and cost displays can contain synthetic values.
- Default effort is high without conversational complexity routing.
- Fallback silently maps Flash selection to `gemini-3.6-flash-*`.
- Current benchmark process cannot reliably distinguish success from fast failure.

Against Claude Code, this audit establishes **no measured ranking** for latency, memory, correctness, or task completion. Publishing one would repeat existing mistake. Comparative claims about competitor architecture and capabilities also need versioned primary evidence.

Etta may have useful native components. Their existence does not prove superior coding-agent performance.

**3. Root causes, with corrections to supplied diagnosis**

**Buffered answer delivery: confirmed.**  
[Runner line 452](/Users/ajaytiwari/Desktop/Projects/etta/crates/etta-cli/src/runner.rs:452) awaits `cmd.output()`, then prints completed stdout. Tokio documents this method as collecting child stdout/stderr into returned output. Async waiting does not itself block executor thread; it blocks delivery through this code path. [Tokio documentation](https://docs.rs/tokio/latest/tokio/process/struct.Command.html)

“Complete terminal freeze with zero feedback” overstates source evidence: runner animates spinner. Accurate description: **no answer content until child finishes**, despite activity animation.

**Per-turn provider spawning: confirmed.**  
Occurs per submitted goal, not per keystroke. Claimed **4–6s attributable to Mach-O/V8/MCP startup** remains unmeasured. Binary size cannot establish startup cost or runtime internals. Separate process launch, application initialization, authentication, connection setup, provider queueing, and generation.

**High default effort: confirmed; exact token consumption unconfirmed.**  
[Defaults](/Users/ajaytiwari/Desktop/Projects/etta/crates/etta-cli/src/runner.rs:130) select Flash High and `"high"`. Primary path passes effort to AGY; fallback supplies 16,384-token budget. Budget is not proof of actual consumption. Google recommends model-specific thinking levels for Gemini 3 onward; numeric budget support must be validated per endpoint/model. [Google thinking documentation](https://ai.google.dev/gemini-api/docs/generate-content/thinking)

**Greeting route: missing in inspected goal path.**  
Everything outside benchmark shortcut reaches live dispatch. Actual reflex decision capability must be tested separately from greeting handling. Returning `"Hello"` locally proves local greeting handling—not JEV inference.

**Existing SSE fallback needs repair, not blind promotion.**  
[Fallback implementation](/Users/ajaytiwari/Desktop/Projects/etta/crates/etta-cli/src/runner.rs:485) has:

- Fresh `reqwest::Client` per dispatch.
- Five-second request timeout.
- Silent model remapping.
- Per-chunk lossy UTF-8 decoding.
- Chunk errors converted into loop termination, followed by success.
- No demonstrated terminal completion validation.
- Text printing without separating thought summaries from answer parts.
- Unconditional printing that can contaminate headless JSON.

Moving fallback above AGY would expose these defects directly.

**Why TTFT matters**

User experiences three separate milestones:

1. **Acknowledgment:** input accepted.
2. **First useful answer:** response begins.
3. **Completion:** work finishes.

Spinner improves acknowledgment only. Streaming lets user start reading, spot misunderstanding, and interrupt sooner. A response beginning at 700ms and ending at 20s can feel substantially faster than response withheld until 16s.

Completion time still matters for tool execution and finished artifacts. Measure both; neither replaces correctness.

**4. Target architecture**

```text
Input → session controller → intent/effort router
                             ├─ deterministic local handler
                             └─ persistent provider adapter
                                       ↓
                         typed incremental events
                                       ↓
                    renderer + journal + usage ledger
```

Reuse existing provider, protocol, reflex, policy, and credential boundaries where valid. Remove separate conversational transport logic from CLI runner.

Session owns shared HTTP client, cancellation, conversation history, selected model, explicit effort override, and turn identifiers. Each request creates its own response stream over reusable transport; “persistent” does not require one endless SSE response. `reqwest::Client` already provides connection pooling when reused. [Reqwest documentation](https://docs.rs/reqwest/latest/reqwest/struct.Client.html)

Proposed event contract:

```text
TurnAccepted
RouteSelected
ProviderRequestStarted
AnswerDelta
ThoughtSummaryDelta
ToolStarted / ToolFinished
UsageReported
TurnCompleted | TurnFailed | TurnCancelled
```

Exactly one terminal event per turn. Incomplete streams never become successful turns.

**I-ETTA-INTERACTIVE-01 — TTFT ceiling**

- Target: **first visible answer content <800ms** for interactive conversational queries.
- Release gate: **p95 <800ms**, with sample count, confidence interval, and fraction exceeding 800ms published.
- Report warm-session, first-session, auth-refresh, and reconnect cohorts separately.
- Status messages, cursor changes, input echo, spinner, and thought summaries do **not** count as answer tokens.
- Separate acknowledgment target: p95 ≤100ms.
- Transport-event-to-render delay: p95 ≤50ms under declared load.

A universal ceiling across public-cloud conditions is unenforceable locally. If required cohort misses target, gate fails. Never replace answer TTFT with acknowledgment timing to manufacture compliance.

**I-ETTA-INTERACTIVE-02 — Native streaming transport**

Primary transport: native async Rust HTTP streaming, HTTP/2 where supported, using supported authenticated provider contract. Alternative: genuinely persistent streaming IPC worker with verified protocol support.

Requirements:

- No `cmd.output()` in interactive provider path.
- Parse complete SSE events across arbitrary byte boundaries.
- Preserve split UTF-8, multiline events, usage metadata, finish reasons, and errors.
- Bounded buffers and backpressure.
- Distinct connection, first-event, idle, and overall deadlines.
- Cancellation stops transport and restores usable prompt.
- Retries cannot silently duplicate output or tool execution.
- Preserve conversation, tool calls/results, policy checks, account isolation, and usage accounting.

Temporary bridge may stream child stdout/stderr concurrently. `AsyncBufReadExt` suits newline-delimited protocols; plain token output needs incremental byte reads because waiting for newline can recreate lag. Bridge remains interim: still violates zero-spawn invariant.

**I-ETTA-INTERACTIVE-03 — Adaptive cognitive effort**

| Tier | Routing | Acceptance |
|---|---|---|
| **1: Reflex** | Deterministic local commands, policy decisions, narrow context-safe greetings | Actual local decision p95 <15ms; no cloud call |
| **2: Conversation** | Simple explanation, short rewrite, ordinary chat | Answer TTFT p95 <800ms; lowest validated suitable thinking setting |
| **3: Deep reasoning** | Complex debugging, architecture, difficult synthesis | Higher effort; responsive cancellation and truthful progress |

For supported numeric-budget models, Tier 2 starts with **0–1,024 thinking tokens**. Otherwise use supported minimal/low setting; record effective configuration. Never imply unsupported hard cap.

Router must consider conversation context. `"hi, inspect this deadlock"` cannot become greeting response. Short security-sensitive commands cannot become reflex actions merely because short.

Explicit user effort override wins. Low-confidence classification takes conservative route. Local greeting handling remains distinct from measured cloud-conversation cohort.

Reasoning indicators show actual provider summaries or reported usage when available. Otherwise show elapsed time and phase. Never fabricate live reasoning-token counters.

**I-ETTA-INTERACTIVE-04 — Zero provider process spawning per turn**

After session initialization, ordinary conversation causes **zero new provider/bridge processes**. Verify through process observations.

Tool commands may legitimately spawn processes; classify separately. Persistent worker crash causes visible recovery state, bounded restart, and accurate accounting. Do not assume AGY supports persistent IPC without proving it.

**Additional integrity invariant**

Unknown usage remains unknown. Estimated usage carries explicit provenance. Offline failure, truncation, cancellation, quota rejection, and protocol failure cannot produce successful completion or fabricated cost.

**5. Senior review and worker execution plan**

Current mandate produces blueprint for subsequent execution. No claim that senior reviews have already happened.

**Round 1 — `gemini-3.1-pro-high`, high effort**

Deliver evidence audit:

- Freeze source SHA, installed binary SHA-256, tool versions, environment, and benchmark artifacts.
- Trace real terminal submission through selected transport to visible answer.
- Build claim ledger: measured, synthetic, contradicted, unsupported.
- Prove model/effort/account mapping and actual usage provenance.
- Verify reflex engine participation and active process-tree memory scope.
- Review harness against false-success, spinner-as-token, and benchmark-recognition attacks.

Each finding requires source location or raw trace, consequence, and proposed gate. Source inspection alone cannot certify live UX.

**Round 2 — `claude-opus-4-6-thinking`, high effort**

Independently challenge Round 1; resolve:

- Native transport versus persistent IPC feasibility.
- Auth, session history, tool execution, and policy parity.
- Numeric thinking-budget compatibility.
- Event contract, cancellation, retries, accounting, and terminal-state rules.
- Statistical thresholds and comparison fairness.
- Final bounded worker packets.

Both seniors review completed implementation too. Worker never certifies own result.

**Bounded worker epics — `gemini-3.8-flash-high`, isolated worktrees**

| Packet | Scope | Required proof |
|---|---|---|
| **E0: Evidence baseline** | Manifest, existing harness audit, corrected claim ledger | Every retained claim maps to raw evidence; missing evidence explicitly marked |
| **E1: Truthful outcomes** | Remove production benchmark shortcuts; typed failure states; usage provenance | Forced auth/network/truncation failures cannot return success or synthetic usage |
| **E2: Independent measurement** | PTY driver, timestamps, process sampling, statistical report | Deliberately buffered fixture fails streaming gate; spinner never satisfies TTFT |
| **E3: Stream protocol** | Typed events, incremental SSE parser, cancellation state machine | Fragmented UTF-8/events, errors, partial completion, backpressure, cancel tests pass |
| **E4: Persistent transport** | Shared client or proven persistent IPC; preserve session/tool semantics | Zero provider spawn across 100 ordinary turns; connection reuse evidence |
| **E5: Routing and effort** | Context-aware local/conversation/deep policy; overrides | Held-out routing cases pass; effective wire settings recorded; quality preserved |
| **E6: Terminal integration** | Incremental rendering, cancel, headless output isolation | PTY captures show answer before completion; prompt recovers after cancel |
| **E7: Independent release audit** | Matched competitor runs, functional verification, publication correction | Seniors reproduce results from pinned artifacts; all failed runs retained |

Order: **E0 → E1/E2 → E3 → E4 → E5/E6 → E7**. Parallel work only with nonoverlapping ownership and agreed interfaces.

Follow current [AlphaBrain lifecycle](/Users/ajaytiwari/Desktop/Projects/alphaBrain/AGENTS.md): admission, deterministic safety review, founder-approved concrete packet, senior research/plan, isolated worker, dual review, approved local promotion. Prior AlphaBrain memory supports immutable packet/digest practice; current pipeline enforcement was not re-executed here.

Each packet must include task ID, base SHA, SHA-256 scope digest, allowed files, dependencies, exact gate commands, resource budget, evidence paths, stop conditions, and rollback. Repairs return through worker pipeline. No direct supervisor implementation edits.

**6. Test harness specification**

Extend existing `testscript/performance/`; keep raw artifacts below its evidence directory.

Proposed components:

| File | Responsibility |
|---|---|
| `manifest.json` | Pinned versions, binaries, models, efforts, corpus, environment |
| `run_interactive.py` | PTY-driven real interactive sessions for each product |
| `collect_process_tree.py` | Provider spawn counts; parent/child/helper memory |
| `stream_fixture.py` | Deterministic delayed, fragmented, failed, and cancelled streams |
| `test_stream_contract.py` | Parser, terminal-state, cancellation, and renderer assertions |
| `report.py` | Quantiles, confidence intervals, failure rates, claim ledger |
| `evidence/<run_id>/` | Raw events, PTY transcripts, resource samples, results, hashes |

Existing `audit_interactive_lag.py` is insufficient: live test covers AGY only, labels first stdout character TTFT, leaves stderr undrained, lacks deadline, and attributes two-run difference solely to thinking.

**Instrumentation**

Record monotonic timestamps for input submission, acknowledgment, route, auth, provider dispatch, headers, first answer delta, first rendered answer, every rendered chunk, last answer, terminal result, and ready prompt.

Measure:

- User-visible answer TTFT.
- Provider answer latency.
- Rendering delay.
- Total completion time.
- Inter-chunk gap p50/p95/max.
- Visible bytes/characters per second.
- Token throughput only with documented tokenizer or actual provider counts.
- Cancel-to-ready latency.
- Process spawns, CPU, memory, failures, retries, and cost.

SSE chunk is not necessarily token. First stdout byte is not necessarily answer. Missing answer means missing TTFT and failed outcome—not substituted completion time.

**Workloads and fairness**

Use two separate comparison tracks:

- **Matched transport:** same backend model, effort, prompt/context, tools, credentials class, output cap.
- **Product experience:** normal defaults for Etta, AGY, Claude Code; record differences without attributing all gains to transport.

Corpus must include greetings, conversational follow-ups, short coding, real file edits, tool use, deep reasoning, long context, ambiguous short prompts, and failure cases.

Randomize paired run order. Separate cold and warm sessions. Minimum 100 measured turns per product in critical conversational cohorts, across at least three sessions; disclose clustering and confidence intervals. Predeclare warmups. Retain timeouts, quota errors, empty answers, retries, and wrong answers.

Memory reporting separates parent RSS, process-tree summed RSS, and shared helper baseline/increment. Summed RSS may double-count shared pages; state that limitation. A status-only process cannot represent active-session memory.

**Release gates**

- Truthful failures and accounting: mandatory.
- Real Tier 1 decision p95 <15ms.
- Tier 2 visible-answer p95 <800ms in declared cohorts.
- Acknowledgment p95 ≤100ms.
- Render delay p95 ≤50ms.
- Cancellation returns usable prompt p95 ≤250ms.
- Zero provider processes spawned per ordinary warm turn.
- Every multi-event fixture renders before final event; lost/duplicated answer content fails.
- Functional task quality meets predeclared noninferiority margin; latency gains cannot purchase incorrect answers.
- No unreviewed reduction in policy enforcement, tool capability, or session continuity.

Required Rust checks after implementation:

```bash
# Check formatting across workspace.
cargo fmt --all -- --check

# Reject Rust lint warnings across targets.
cargo clippy --workspace --all-targets -- -D warnings

# Run workspace regression tests.
cargo test --workspace
```

Senior packets must add exact Python lint, fixture, PTY, and live benchmark commands once harness interfaces exist. Missing executable gates block worker admission.

**Release decision: Etta has a credible optimization path, but no defensible “interactive supremacy” claim today. First repair truthfulness; then prove streaming, routing, quality, and latency through independent end-to-end evidence.**

