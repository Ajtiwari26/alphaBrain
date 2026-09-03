# AlphaBrain Workspace Rules & Execution Standards

1. **Mandatory Senior Review After Completion**:
   Always review completed tasks from senior engineering review after completion via Pro or Opus depending on limit remaining calculated via `agy-switch list` and `agy-switch check <email>`.
   - **Mathematical Baseline (Opportunity-Cost / Earliest-Deadline Scheduling):** Calculate the Utility Score ($U$) for each account:
     $$U_i = \begin{cases} -\infty, & \text{if } W_i \le 0.0 \\ \left[ \frac{\ln(1 + W_i)}{T_{w,i} + 1.0} \right] \cdot \left( \sqrt{\max(0, F_i)} + \frac{2.0}{T_{f,i} + 1.0} \right), & \text{if } W_i > 0.0 \end{cases}$$
     where $W_i$ and $F_i$ are weekly and 5-hour limits (%), $T_{w,i}$ is days/hours to weekly reset, and $T_{f,i}$ is hours to 5-hour reset.
   - **Smooth Non-Disqualifying 5-Hour Scaling:** An account is disqualified ($-\infty$) ONLY when weekly quota is completely zero ($W_i \le 0$). Low 5-hour limits never disqualify an account; the $\frac{2.0}{T_{f,i} + 1.0}$ term smoothly rewards accounts whose 5-hour limit refreshes sooner.
   - You MUST `agy-switch` to the account with $\arg\max U_i$ and invoke `claude-opus-4-6-thinking`.
   - **Mid-Level Fallback:** If and ONLY IF all accounts have $W_i \le 0.0\%$ (all $U_i = -\infty$), fallback to Gemini Pro (`gemini-3.1-pro-high`) as a mid-level engineer for the review.

2. **Canonical Architecture & Conflict Resolution Authority (Opus Exclusive Authoring)**:
   - `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` is authored and maintained EXCLUSIVELY by Claude Opus (`claude-opus-4-6-thinking`).
   - All Pro and Flash models, executors, and subagents have STRICT READ-ONLY access to this file and MUST consult it for architectural guidance and system design.
   - In case of any discrepancy or conflict, `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` is the supreme source of truth.
   - Under no circumstances may any agent modify `alphaBrain/alpha_meet/` (strictly immutable).

3. **Clean Task Lifecycle**:
   Always clean up and kill unwanted or no longer in-use background tasks (like lingering `tail -f`, sleep loops, or temporary monitor tasks) using `manage_task` before stopping or completing things so no dangling tasks are left running.

4. **Multi-Agent SDLC & Graph Integration**:
   - Maintain workspace clean: every test script must be under `testscript/` directory.
   - Code review graph MCP must be consulted for context to prevent token waste and preserve architectural integrity.
   - Every terminal command or curl command must have a clear commented explanation string describing what it achieves.
