# AlphaBrain Workspace Rules & Execution Standards

1. **Mandatory Senior Review After Completion**:
   Always review completed tasks from senior engineering review after completion via Pro or Opus depending on limit remaining calculated via `agy-switch list` and `agy-switch check <email>`.
   - **Mathematical Baseline (Tiered Opportunity-Cost / Earliest-Deadline Scheduling):** Calculate the Utility Score ($U$) for each account across 3 strict priority tiers:
     - **Tier 1 (Idle First):** If an account is untouched ($W_i \ge 99.0\%$ with weekly countdown timer unstarted), $U_i = 1000.0 + F_i$. These accounts MUST be routed to first for productive tasks to "break the seal" and trigger their 7-day weekly refresh countdown clock.
     - **Tier 2 (Expiring $\le 2$ Days):** If $0 < T_{w,i} \le 2.0\text{ days}$ and $W_i > 0.0$, $U_i = 100.0 + \left[ \frac{100.0}{T_{w,i} + 0.1} \right] \cdot \left[ \frac{\sqrt{\max(0.1, W_i)}}{10.0} \right]$. Prioritizes consuming expiring quota before the weekly window refreshes.
     - **Tier 3 (Normal OC-EDS Rotation):** For all other active accounts ($T_{w,i} > 2.0\text{ days}$ and $W_i > 0.0$):
       $$U_i = \left[ \frac{\ln(1 + W_i)}{T_{w,i} + 1.0} \right] \cdot \left( \sqrt{\max(0, F_i)} + \frac{2.0}{T_{f,i} + 1.0} \right)$$
     - **Tier 4 (Disqualified):** If $W_i \le 0.0\%$, $U_i = -\infty$.
   - **Smooth Non-Disqualifying 5-Hour Scaling:** An account is disqualified ($-\infty$) ONLY when weekly quota is completely zero ($W_i \le 0$). Low 5-hour limits never disqualify an account.
   - You MUST `agy-switch` to the account with $\arg\max U_i$ (or run `agy-switch plan`) and invoke `claude-opus-4-6-thinking`.
   - **Mid-Level Fallback:** If and ONLY IF all accounts have $W_i \le 0.0\%$ (all $U_i = -\infty$), fallback to Gemini Pro (`gemini-3.1-pro-high`) as a mid-level engineer for the review.

2. **Canonical Architecture & Conflict Resolution Authority (Opus Exclusive Authoring)**:
   - `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` is authored and maintained EXCLUSIVELY by Claude Opus (`claude-opus-4-6-thinking`).
   - All Pro and Flash models, executors, and subagents have STRICT READ-ONLY access to this file and MUST consult it for architectural guidance and system design.
   - In case of any discrepancy or conflict, `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` is the supreme source of truth.
   - Under no circumstances may any agent modify `alphaBrain/alpha_meet/` (strictly immutable).

3. **Clean Task Lifecycle**:
   Always clean up and kill unwanted or no longer in-use background tasks (like lingering `tail -f`, sleep loops, or temporary monitor tasks) using `manage_task` before stopping or completing things so no dangling tasks are left running.

4. **Multi-Agent SDLC & Graph Integration**:
   - **Strictly On-Demand:** The SDLC pipeline is never run automatically for simple questions, code inspections, or minor inquiries. Invoke the `multi-agent-sdlc` skill ONLY when the user explicitly instructs you to do so (by mentioning 'sdlc' or requesting an engineering pipeline).
   - When invoked, execute across the 4 modular modes:
     1. **`sdlc-full` (Full Pipeline Mode):** Executes the complete autonomous pipeline (`alpha_core.triage_cli`: admit -> review -> approve -> senior-plan -> worker-cycle on `gemini-3.8-flash-high` in isolated worktree -> senior-review -> merge).
     2. **`sdlc-worker` (Implementation Mode):** Autonomous coding via `gemini-3.8-flash-high` (`--effort high`) in an isolated Git worktree; runs tests and lint; zero edits on main (Invariant I-68).
     3. **`sdlc-seniors` (Standard Senior Review Mode):** Mandatory 2-Round debate between Gemini 3.1 Pro High (`--effort high` Round 1 audit) and Claude Opus 4.6 Thinking (`--effort high` Round 2 synthesis via `agy-switch` Tiered OC-EDS). Does NOT require Astra.
     4. **`sdlc-astra` (On-Demand Tier 0 Blueprint Mode):** `gpt-6-astra` Master Architectural Blueprint (MAB); strictly quarantined and SKIPPED by default. MUST ask user for explicit confirmation before invoking. Invocation protocol via Codex CLI:
        ```bash
        codex exec --ephemeral --skip-git-repo-check --cd /tmp -m gpt-6-astra -c 'model_reasoning_effort="medium"' -o <output_file> < <prompt_file>
        ```
        (Always include `--ephemeral --skip-git-repo-check --cd /tmp` to isolate execution from repo token bloat and protect 5h quota).
   - Maintain workspace clean: every test script must be under `testscript/` directory.
   - Code review graph MCP must be consulted for context to prevent token waste and preserve architectural integrity.
   - Every terminal command or curl command must have a clear commented explanation string describing what it achieves.
   - Maintain the single living system truth in `ALPHABRAIN_SYSTEM_TRUTH.md` and enforce Architectural Garbage Collection (Invariants I-69 to I-72).

5. **Strict Autonomous Self-Development Invariant (Zero Direct Manual Edits)**:
   - **NO DIRECT MANUAL CODE MODIFICATIONS**: Assistants (Antigravity, Gemini, Claude, etc.) must NEVER manually edit task implementation code, tests, or features directly in the workspace working tree.
   - **STRICT SELF-DEVELOPMENT DISPATCH**: All features, modifications, bug fixes, and review repairs MUST be executed exclusively by AlphaBrain's autonomous self-development pipeline:
     1. **Admit**: Task or repair admitted into triage queue (`.venv/bin/python -m alpha_core.triage_cli admit`).
     2. **Safety Review**: Deterministic SafetyGate evaluation (`.venv/bin/python -m alpha_core.triage_cli review <task_id>`).
     3. **Founder Approval**: Operator sign-off (`.venv/bin/python -m alpha_core.triage_cli approve <task_id>`).
     4. **Autonomous Senior Research**: Web & GitHub-grounded research via gemini-3.1-pro-high (`.venv/bin/python -m alpha_core.triage_cli senior-research <task_id>`).
     5. **Autonomous Planning**: Blueprint generation (`.venv/bin/python -m alpha_core.triage_cli senior-plan <task_id>`).
     6. **Autonomous Worker Dispatch**: AGY coding agent dispatched inside an isolated Git worktree (`.venv/bin/python -m alpha_core.triage_cli worker-cycle <task_id>`). Worker executes exclusively on `gemini-3.8-flash-high` (`--effort high`) for high-velocity tool/test loops (~160 TPS, 90.8% Terminal-Bench). All code edits, test additions, and gate executions occur inside this isolated worktree by the AGY worker.
     7. **Senior Engineering Review**: Mandatory 2-Round debate between Gemini 3.1 Pro High and Claude Opus 4.6 Thinking (`.venv/bin/python -m alpha_core.triage_cli senior-review <task_id>`). If repairs are required, the repair instructions are fed back into AlphaBrain's autonomous retry cycle—NEVER manually patched by the supervisor.
     8. **Autonomous Merge**: Atomic fast-forward merge into main (`.venv/bin/python -m alpha_core.triage_cli merge <task_id>`) only after unanimous senior approval.
   - The supervisor's role is strictly orchestration, monitoring, and operator feedback—never direct coding or bypass.

6. **Multi-Account CLI Execution & Subagent Isolation Invariant**:
   - **Interactive GUI Session Protection**: The user account logged into the active Antigravity 2.0 GUI must NEVER be depleted by spawning heavy background subagent loops (`invoke_subagent`). Subagents share the active session's quota, transmitting duplicated transcript and system context across every turn, which rapidly exhausts the 5-hour limit.
   - **Rotated AGY Worker Dispatch**: Autonomous worker coding cycles must be dispatched exclusively via `agy` CLI (`alpha_core.triage_cli worker-cycle` or headless `agy` processes) executed on the other 7 available accounts rotated via `agy-switch switch <account>`.
   - **Controlled Model & Bounded Context**: Dispatches must route to accounts with 100% available Gemini 5h quota, utilizing `gemini-3.8-flash-high` in isolated git worktrees with strict, bounded prompts and toolsets to avoid token bloat and ensure the entire 5-hour limit is never prematurely exhausted.

7. **Strict Effort Argument Rules (`--effort`)**:
   - **Gemini Models REQUIRE Explicit Effort**: Whenever invoking Gemini models via CLI (e.g. `gemini-3.8-flash-high`, `gemini-3.1-pro-high`), you MUST ALWAYS explicitly provide the `--effort` argument (typically `--effort high`, or `--effort medium` / `--effort low` as appropriate). Never omit the `--effort` flag when executing Gemini models.
   - **Claude Models NEVER Take Effort**: Claude models (e.g. `claude-opus-4-6-thinking`) do NOT have an `--effort` argument. Never pass the `--effort` flag when invoking Claude models.


