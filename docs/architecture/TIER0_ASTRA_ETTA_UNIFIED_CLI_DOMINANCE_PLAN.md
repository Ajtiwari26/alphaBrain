# TIER 0 ASTRA SDLC SPECIFICATION: ETTA UNIFIED CLI DOMINANCE BLUEPRINT
**Document ID:** `MAB-ETTA-UNIFIED-DOMINANCE-002`  
**Target Milestone:** DeployMate Etta Autonomous Engine v0.2.0  
**Authorship Authority:** AlphaBrain Multi-Agent SDLC Protocol (Tier 0 Grand Architect Track — Astra `gpt-6-astra`)  
**Scope Directive:** Complete Functional Dominance over Claude Code CLI, OpenAI Codex CLI, and Google Antigravity (`agy`) across Headless Browser, Computer Use, Local JEV Reflex, Open LSP 3.17, and Context Efficiency  
**Date:** 2026-09-18  

---

## 1. Executive Directive & Architectural Mandate

Modern AI coding CLIs exhibit three distinct generational paradigms, each hobbled by severe architectural compromises:
1. **Anthropic Claude Code CLI**: Superb permission ergonomics and streaming diff UX, but throttled by heavy single-threaded Node.js runtimes (~180MB RAM), single-provider API lock-in, and remote-only micro-decision loops that wait 1.5–3s for every trivial check.
2. **OpenAI Codex CLI**: Capable headless browser automation, but crippled by severe process bloat (Python + Playwright container requiring 1GB+ RAM), lack of Retina 2.0x DPI compensation (causing cursor misclicks), and an inverted tool execution lifecycle that returns "success" before validating DOM mutation.
3. **Google Antigravity (`agy`) CLI**: Fast raw token throughput (~170 TPS) and multi-account credential pooling, but crippled by 79,103-token context bloat per request, an unredacted credential wire boundary, and rigid coupling to a closed Electron desktop app daemon.

### The Mission of DeployMate Etta v0.2.0
`etta` solves all three paradigms simultaneously through a **zero-dependency, pure-Rust, JEV-First Bi-Cameral Architecture**.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           DEPLOYMATE ETTA v0.2.0 CORE                          │
├────────────────────────────────────────────────────────────────────────────────┤
│  1. JEV SYSTEM 1 (<15ms Local Rust Reflex — 0 Tokens)                          │
│     ├── Local SafetyGate & 4-Tier Permission Matrix (Default/Accept/Bypass/Plan)│
│     ├── Path Boundary Sandbox & POSIX Process Groups (setpgid(0, 0))            │
│     └── AST Blast-Radius Filtering (Code Review Graph ~100 tokens vs 79k)       │
├────────────────────────────────────────────────────────────────────────────────┤
│  2. NATIVE HEADLESS BROWSER & COMPUTER USE (Zero Playwright / Zero Electron)   │
│     ├── Loopback-Only Async CDP (127.0.0.1) — <10MB RSS Footprint               │
│     ├── Retina 2.0x Sub-Pixel DPI Transform — Strict Boundary Validation        │
│     ├── ADR-005 Wire Redaction — Masks auth headers & cookies to [REDACTED]     │
│     └── ADR-006 Disconnect Reconciliation & Pre/Post DOM Evidence Assertions    │
├────────────────────────────────────────────────────────────────────────────────┤
│  3. DUAL-TIER UNIVERSAL CODE INTELLIGENCE                                      │
│     ├── Open LSP 3.17 JSON-RPC over stdio (rust-analyzer, pyright, gopls)       │
│     ├── Seamless fallback to Google AgentAPI where present                      │
│     └── Programmatic REPL Batch Engine for multi-file operations                │
├────────────────────────────────────────────────────────────────────────────────┤
│  4. HIGH-AVAILABILITY STATE & CLOUD FEDERATION                                 │
│     ├── Sub-4ms SQLite CAS Transactional Undo / Rollback Journal                │
│     └── Mathematical OC-EDS Live Rotation across 8 Google AI Pro Accounts       │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Foundational Architectural Invariants (INV-ETTA-11 to INV-ETTA-20)

- **`INV-ETTA-11` (Zero-Playwright Native CDP Engine)**:
  All browser automation MUST execute via pure-Rust async Chrome DevTools Protocol (`crates/etta-browser`) over local loopback (`127.0.0.1`). External heavy automation runners (Playwright, Puppeteer, Selenium) and Electron wrappers are strictly prohibited. Peak process RSS must remain `<15 MB`.
- **`INV-ETTA-12` (Retina 2.0x Sub-Pixel DPI Calibration)**:
  All mouse, touch, and visual pointer interactions MUST pass through `DisplayGeometry::to_physical()`. Logical points $(x, y)$ are mathematically scaled by the active hardware factor $S$ (e.g. 2.0 on Apple Retina) and clamped to display boundaries:
  $$\text{physical\_x} = x \times S, \quad \text{physical\_y} = y \times S$$
- **`INV-ETTA-13` (ADR-005 Wire Redaction Boundary)**:
  All network traffic headers, session cookies, Bearer tokens, and sensitive query parameters captured during browser or HTTP actions MUST be masked with `[REDACTED]` at the wire level before serialization into LLM prompt context.
- **`INV-ETTA-14` (ADR-006 Postcondition Verification & Reconciliation)**:
  A browser click, navigation, or form submission MUST NOT return success based on event dispatch alone. The engine must assert DOM postcondition evidence (URL mutation, element presence, or tree hash update). In-flight network drops or disconnects MUST yield `ActionOutcome::ExecutedUnverified` or `ActionOutcome::Unknown`, never false `Succeeded` or false `Failed`.
- **`INV-ETTA-15` (JEV System 1 <15ms Zero-Token Reflex)**:
  Command syntax sanitization, path traversal checks, file permission tiers, loop detection, and regex linting MUST execute locally in Rust within `<15 ms` consuming zero LLM tokens. System 2 (remote foundation models) is invoked strictly for semantic synthesis and high-level strategy.
- **`INV-ETTA-16` (Dual-Tier Universal LSP 3.17)**:
  Code intelligence MUST speak standard LSP 3.17 JSON-RPC over stdio with installed language servers (`rust-analyzer`, `pyright`, `gopls`, `typescript-language-server`). If a proprietary `AgentAPI` server is present and healthy, it is queried first; upon absence or error, the engine seamlessly falls back to standard LSP without failing the turn.
- **`INV-ETTA-17` (AST Minimal Blast-Radius Context)**:
  Prompts must NOT exceed 3,000 base tokens. Context injection MUST query Tree-sitter structural dependencies (`code-review-graph`) to supply only affected callers, callees, and test contracts (~100 tokens), preventing the 79k-token bloat observed in `agy`.
- **`INV-ETTA-18` (Sub-4ms SQLite CAS Transactional Undo)**:
  Every file mutation and state delta MUST be recorded in an atomic SQLite CAS journal. If post-execution compiler checks or tests fail, workspace state must be atomically rewindable in `<5 ms` without disturbing uncommitted user modifications.
- **`INV-ETTA-19` (Tiered OC-EDS Multi-Account Quota Rotation)**:
  Google Cloud Code PA calls must route dynamically across all 8 Google AI Pro accounts according to smooth Tiered Opportunity-Cost / Earliest-Deadline Scheduling:
  $$U_i = \left[ \frac{\ln(1 + W_i)}{T_{w,i} + 1.0} \right] \cdot \left( \sqrt{\max(0, F_i)} + \frac{2.0}{T_{f,i} + 1.0} \right)$$
- **`INV-ETTA-20` (Batch REPL Mode Acceleration)**:
  For bulk file edits, tests, and refactors exceeding 5 sequential operations, the engine MUST offer a programmatic REPL batch execution path, collapsing multiple roundtrips into a single transactional execution block.

---

## 3. Detailed Subsystem Specifications

### Subsystem A: `crates/etta-browser` (Native Headless Browser & Computer Use)
1. **Module Architecture**:
   - `cdp.rs`: Pure async WebSocket client connecting to Chrome DevTools endpoint (`http://127.0.0.1:9222/json/version`). Supports page navigation, DOM inspection, element query, script evaluation, and screenshot capture.
   - `desktop.rs`: Native macOS/Linux screen geometry coordinator. Implements `DisplayGeometry` (Retina 2.0x scaling), `verify_freshness(<=1000ms)` for screenshots, and `verify_accessibility()` with clean error handling (no infinite loops).
2. **Tool Primitives Exported to `etta-tools`**:
   - `browser_navigate(url: String, timeout_ms: Option<u64>)`
   - `browser_click(selector: Option<String>, coords: Option<(f64, f64)>, verify_postcondition: Option<String>)`
   - `browser_type(selector: Option<String>, text: String, press_enter: Option<bool>)`
   - `browser_screenshot(max_age_ms: Option<u64>) -> DesktopScreenshot`
   - `browser_evaluate(expression: String) -> Value`

---

### Subsystem B: `crates/etta-language` (Dual-Tier LSP 3.17 & Code Intelligence)
1. **Module Architecture**:
   - `lsp.rs`: Asynchronous JSON-RPC client running over child process stdio pipes. Tracks document versions, caches compiler diagnostics with stale-revision rejection, and executes `goToDefinition`, `hover`, `documentSymbol`, and `findReferences`.
   - `agentapi.rs`: Dual-Tier `LanguageBridge`. Evaluates health of optional Tier 2 AgentAPI; upon any failure, instantly falls back to Tier 1 standard LSP.
2. **Tool Primitives Exported to `etta-tools`**:
   - `lsp_diagnostics(file_path: String) -> DiagnosticReport`
   - `lsp_definition(file_path: String, line: u32, character: u32) -> Vec<DefinitionLocation>`
   - `lsp_hover(file_path: String, line: u32, character: u32) -> Option<HoverResult>`
   - `lsp_symbols(file_path: String) -> Vec<DocumentSymbol>`

---

### Subsystem C: `crates/etta-tools` (Unified 30+ Tool Registry Expansion)
1. **Registry Composition**:
   - Filesystem & AST: `view_file`, `write_to_file`, `replace_file_content`, `list_dir`, `grep_search`, `find_by_name`.
   - Terminal & Task: `run_command`, `manage_task`, `schedule`.
   - Multi-Agent: `invoke_subagent`, `define_subagent`, `manage_subagents`, `send_message`.
   - MCP Protocol: `call_mcp_tool`, `list_resources`, `read_resource`.
   - Web & User UI: `search_web`, `read_url_content`, `generate_image`, `ask_question`, `finish`.
   - **NEW: Native Browser Suite**: `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot`, `browser_evaluate`.
   - **NEW: Code Intelligence Suite**: `lsp_diagnostics`, `lsp_definition`, `lsp_hover`, `lsp_symbols`.

---

## 4. Implementation Work Packets (WP-ETTA-06 to WP-ETTA-08)

- **`WP-ETTA-06` (`crates/etta-tools` & `crates/etta-browser`)**:
  Connect `etta-browser` into `etta-tools`. Implement the 5 browser tool handlers with loopback CDP, Retina 2.0x DPI transforms, ADR-005 redaction, and ADR-006 postcondition checks.
- **`WP-ETTA-07` (`crates/etta-tools` & `crates/etta-language`)**:
  Connect `etta-language` into `etta-tools`. Implement the 4 LSP tool handlers with dual-tier fallback and stdio JSON-RPC.
- **`WP-ETTA-08` (`crates/etta-cli` & Verification)**:
  Expose new browser and LSP tools in the Ratatui HUD and CLI runner. Execute end-to-end integration tests and benchmark against `agy`.

---

**Tier 0 Blueprint Status:** AUTHORED & RATIFIED.  
**Handoff Directive:** Proceed to Tier 1 Senior Engineering Review (`sdlc-seniors`: Round 1 Gemini 3.1 Pro High audit, Round 2 Claude Opus 4.6 Thinking synthesis).
