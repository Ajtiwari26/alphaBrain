# CANONICAL SENIOR DIRECTIVE: ETTA v0.2.0 UNIFIED CLI DOMINANCE
**Document ID:** `SENIOR-DIR-ETTA-DOMINANCE-002`  
**Target Milestone:** DeployMate Etta Unified Agent Engine v0.2.0  
**Authorship Authority:** AlphaBrain Multi-Agent SDLC Protocol (Claude Opus 4.6 Thinking — Senior Synthesis Authority)  
**Prior Audits:**  
- Tier 0 Grand Blueprint: `MAB-ETTA-UNIFIED-DOMINANCE-002` (GPT-6 Astra)  
- Round 1 Senior Audit: `AUDIT-ETTA-001` (Gemini 3.1 Pro High)  
**Date:** 2026-09-18  

---

## 1. Adversarial Cross-Examination & Executive Synthesis

Claude Opus 4.6 Thinking has evaluated the Tier 0 Astra Blueprint alongside Gemini 3.1 Pro High's Round 1 Senior Audit. The overarching architectural strategy—replacing heavy, fragile dependencies (Playwright, Puppeteer, Electron) with a pure-Rust, JEV-first bi-cameral engine—is **fully ratified**.

However, the systems engineering gaps highlighted by Gemini 3.1 Pro High represent critical failure modes if left unaddressed. Specifically:
1. **Re-connection Penalty**: Re-spawning an LSP server or reconnecting a CDP WebSocket on every tool call would balloon tool latency from <15ms to 800ms+, destroying Etta's speed advantage. Persistent shared session actors are mandatory.
2. **Tokio Scheduling Deadlocks**: Standard blocking I/O on stdio pipes or holding mutexes across await points will freeze the async reactor under high-concurrency tool execution.
3. **Sub-Pixel Coordinate Panics**: Floating-point Retina scaling without discrete integer clamping causes off-by-one out-of-bounds panics at the display perimeter.
4. **False Failures on Focus/Select**: Enforcing DOM mutation evidence on non-mutating actions (like focusing an input or selecting text) causes false errors.
5. **Disk Commit Latency**: Standard SQLite rollback journals with synchronous=FULL cannot reliably achieve <4ms rollback due to OS fsync barriers.

---

## 2. Binding Architectural Amendments (MA-01 to MA-06)

The following six amendments are **binding on all worker implementations**:

### MA-01: Shared Persistent Session Actor Container (`etta-tools`)
`ToolRegistry` MUST maintain long-lived, persistent connection pools for stateful subsystems:
- **CDP Session**: Wrapped in `Arc<tokio::sync::RwLock<Option<CdpSession>>>` to maintain open WebSocket connections across multiple tool turns.
- **LSP Session**: Wrapped in `Arc<tokio::sync::RwLock<Option<LanguageBridge>>>` to maintain active `rust-analyzer` / `pyright` stdio processes.
- Connection failure MUST trigger exponential backoff auto-reconnect (up to 3 attempts, max 500ms total) rather than failing the agent turn.

### MA-02: Tokio-Native Async Process & Channel Concurrency (`etta-language`, `etta-browser`)
- All child process spawning MUST use `tokio::process::Command`.
- Stdio reader loops and CDP WebSocket frame reception MUST execute in isolated background `tokio::spawn` tasks communicating with tool handlers through bounded `tokio::sync::mpsc` channels (`buffer_size: 128`).
- Under no circumstances may `std::sync::Mutex` or blocking `std::io` be held across `.await` points.

### MA-03: Discrete Retina Coordinate Rounding & Display Clamping (`INV-ETTA-12`)
The physical coordinate transform in `crates/etta-browser/src/desktop.rs` is formally amended:
```rust
pub fn to_physical(&self, logical_x: f64, logical_y: f64) -> Result<(i32, i32), DesktopError> {
    if logical_x < 0.0 || logical_x > self.logical_width || logical_y < 0.0 || logical_y > self.logical_height {
        return Err(DesktopError::OutOfBounds { x: logical_x, y: logical_y, screen_width: self.logical_width, screen_height: self.logical_height });
    }
    let max_px_w = (self.logical_width * self.scale_factor).round() as i32;
    let max_px_h = (self.logical_height * self.scale_factor).round() as i32;
    let px_x = (logical_x * self.scale_factor).round().clamp(0.0, (max_px_w - 1).max(0) as f64) as i32;
    let px_y = (logical_y * self.scale_factor).round().clamp(0.0, (max_px_h - 1).max(0) as f64) as i32;
    Ok((px_x, px_y))
}
```

### MA-04: Serialization Boundary Redaction (`INV-ETTA-13`)
Redaction does not occur at the raw TCP layer. Instead, it is strictly enforced at the **CDP event serialization boundary**:
- When network request/response headers are serialized for model prompt injection, a structured key-matcher replaces values of case-insensitive matches (`authorization`, `cookie`, `set-cookie`, `x-api-key`, `proxy-authorization`) with `"[REDACTED]"`.

### MA-05: Configurable Postcondition Verification Strategy (`INV-ETTA-14`)
Browser actions accept an explicit `VerificationStrategy`:
```rust
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum VerificationStrategy {
    None,
    StateUnchanged,
    ExpectedMutation { selector: String, timeout_ms: u64 },
    Navigation { expected_url_prefix: String, timeout_ms: u64 },
}
```
If `VerificationStrategy::None` is specified, the action succeeds immediately upon verified dispatch. If `StateUnchanged` is expected (e.g. element focus), absence of DOM changes yields `ActionOutcome::Verified` rather than an error.

### MA-06: High-Performance SQLite WAL Configuration (`INV-ETTA-18`)
To guarantee sub-4ms transactional state recovery, the SQLite CAS rollback journal MUST initialize with:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -64000;
```

---

## 3. Work Packet Allocation for Autonomous Worker Dispatch

### WP-ETTA-06: Native Headless Browser Tool Suite (`crates/etta-tools` + `crates/etta-browser`)
- **Assigned Worker**: `gemini-3.8-flash-high` (`--effort high`)
- **Scope**:
  1. Add `etta-browser` as dependency in `crates/etta-tools/Cargo.toml`.
  2. Implement `crates/etta-tools/src/browser.rs` with `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot`, `browser_evaluate`.
  3. Wire persistent `CdpSession` state container with `MA-01`, `MA-03`, `MA-04`, and `MA-05`.
  4. Implement unit & integration tests under `crates/etta-tools/tests/browser_tools_tests.rs`.

### WP-ETTA-07: Dual-Tier Universal LSP Tool Suite (`crates/etta-tools` + `crates/etta-language`)
- **Assigned Worker**: `gemini-3.8-flash-high` (`--effort high`)
- **Scope**:
  1. Add `etta-language` as dependency in `crates/etta-tools/Cargo.toml`.
  2. Implement `crates/etta-tools/src/language.rs` with `lsp_diagnostics`, `lsp_definition`, `lsp_hover`, `lsp_symbols`.
  3. Wire persistent `LanguageBridge` with `MA-01` and `MA-02` (Tokio async process channels).
  4. Implement unit & integration tests under `crates/etta-tools/tests/language_tools_tests.rs`.

### WP-ETTA-08: HUD Integration & Head-to-Head Verification (`crates/etta-cli`)
- **Assigned Worker**: `gemini-3.8-flash-high` (`--effort high`)
- **Scope**:
  1. Register all 9 new browser and LSP tools in `etta-tools::registry::ToolRegistry`.
  2. Compile release binary to `~/.cargo/bin/etta`.
  3. Run live end-to-end verification script testing browser automation, LSP definitions, and token speed.

---

**Directive Status:** RATIFIED & BINDING  
**Senior Lead Architect:** Claude Opus 4.6 Thinking  
**Execution Authority:** Multi-Agent SDLC Self-Development Worker Cycle (`alpha_core.triage_cli`)
