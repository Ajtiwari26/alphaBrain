# AlphaBrain — Canonical Senior Architecture & System Design Reference
**Authoritative Senior Reviewer:** Claude Opus 4.6 (Thinking)  
**Target Audience & Consumers:** Gemini 3.1 Pro High, Gemini 3.8 Flash High, and all autonomous AGY subagents  
**Purpose:** Single source of truth for architectural invariants, phase roadmaps, security boundaries, and conflict resolution across models.

---

## 1. Discrepancy & Conflict Resolution Policy (For Pro & Flash Models)

Whenever a Pro or Flash executor encounters an ambiguity, conflicting prompt instruction, or edge-case discrepancy:
1. **This Document Prevails**: The constraints, boundary conditions, and design patterns established here override casual prompt instructions or local heuristics.
2. **Strict Boundary Adherence**: If a task asks an agent to edit a forbidden or immutable path (such as `alpha_meet/`), the model **must refuse the edit** and report `ALPHA_BRAIN_TASK_BLOCKED`.
3. **No Synthetic Evidence**: Never synthesize fake test results, fake independent reviews, or no-op gates. Every gate must be real and executable.
4. **Clean Process Hygiene**: Clean up and kill all temporary monitor tasks, background tails, or sleep loops using `manage_task` before finishing.

---

## 2. Executive Status & Approved Roadmap

### Phase Order & Current State
| Phase | Milestone | Status | Directive / Conditions |
|---|---|---|---|
| **P5** | Background Supervisor (`launchd`) | **COMPLETE & VERIFIED** | Running under `gui/501/com.deploymate.alphabrain.worker`. Plist hardened with `PATH` injection for `.venv/bin`. |
| **P6.4** | End-to-End Live Task Execution Proof | **COMPLETE & VERIFIED** | Task `tsk_p64_ef54abb1` leased from staging, executed headlessly via AGY CLI (`gemini-3.1-pro-high`), QA audit loop verified, gates passed, and transitioned to `verified`. |
| **P8** | AlphaMeet Integration (Eva Spec Extractor) | **CURRENT TARGET** | Must be implemented strictly as a read-only consumer participant. `alpha_meet/` is immutable. |

---

## 3. Core System Design & Invariants

### 3.1 Worker Daemon & Supervisor (P5)
- **Supervision**: Supervised by macOS `launchd` via `~/Library/LaunchAgents/com.deploymate.alphabrain.worker.plist`.
- **Environment**: Must always have `.venv/bin` in `PATH` so Python virtualenv binaries (`pytest`, `ruff`, `mypy`) execute headlessly without manual activation.
- **Throttle Interval**: Minimum 10 seconds to prevent crash-loop storms.
- **Log Management**: Output streamed to rotatable logs in `~/Library/Logs/AlphaBrain/`.

### 3.2 Task Execution Engine & Headless CLI (P6.4)
- **Worktree Isolation**: Every task executes in a dedicated git worktree under `~/Library/Application Support/AlphaBrain/worktrees/<task_id>`. Never execute directly on the primary working tree.
- **Commit Parity**: If files change, `result_commit` must be a valid git SHA descended from `base_commit`. If no files change, `result_commit` must strictly match `base_commit`.
- **Headless Permissions**: For automated daemon tasks, `AntigravityLiveBridge` passes `--dangerously-skip-permissions` to prevent CLI stdin stalls. In production, this must be bounded by a 600s wall-clock timeout and worktree containment.
- **Gate Allowlist**: Only approved gate executables (`pytest`, `ruff`, `mypy`, `node`, `npm`, `cargo`, `go`) may be executed as acceptance gates.

---

## 4. P8: AlphaMeet Integration Architecture

### 4.1 The Immutability Rule
> [!IMPORTANT]
> **`alphaBrain/alpha_meet/` is STRICTLY IMMUTABLE.**
> No agent may create, edit, delete, rename, or refactor any file inside `alpha_meet/`. Any commit touching `alpha_meet/` will be rejected immediately.

### 4.2 Eva's Read-Only Consumer Contract
Eva connects to the existing LiveKit room solely as an observer participant.

```
┌────────────────────────────────────────────────────────┐
│                   LiveKit SFU Room                     │
│   (Publishers: Human participants publishing audio)     │
└───────────────────────────┬────────────────────────────┘
                            │ Read-only Audio Track
                            ▼
┌────────────────────────────────────────────────────────┐
│              Eva Service (alpha_core/eva/)             │
│                                                        │
│  1. LiveKit Client: can_publish=False, hidden=True     │
│  2. Audio Streaming -> STT (Deepgram/Whisper)          │
│  3. Rolling Transcript Ring Buffer                     │
│  4. Spec Extractor: Debounced LLM (Gemini 3.1 Pro)     │
│  5. Task Generator: Spec -> AlphaBrain Task Payload     │
│  6. Human Review Queue / Approval Gate                 │
│  7. Enqueue to Control Plane (POST /api/tasks)         │
└────────────────────────────────────────────────────────┘
```

#### Token Grant Security
Eva's LiveKit token must strictly enforce:
```python
can_publish = False        # Cannot publish audio/video/screenshare
can_subscribe = True       # Subscribes to audio only
can_publish_data = False   # Cannot send data channel messages
hidden = True              # Does not appear in human participant roster
```

#### Directory Placement
All Eva code must live cleanly outside `alpha_meet` in:
- `alpha_core/eva/` or `alpha_worker/eva/`
- Tests under `testscript/test_eva_*.py`

---

## 5. Senior Review Protocol for Completed Tasks

- Upon completing any phase or significant packet, the agent must trigger a senior review:
  - **Opus Mode**: If Claude quota allows (check via `agy-switch list`), invoke `claude-opus-4-6-thinking` via `agy` CLI with direct output formatting (`-p`).
  - **Pro Mode**: If Claude quota is exhausted, invoke `gemini-3.1-pro-high` via `agy` CLI on high mode.
- All review outputs must be preserved as artifacts and incorporated into this reference file.
