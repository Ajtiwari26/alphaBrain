# AlphaBrain Workspace Rules & Execution Standards

1. **Mandatory Senior Review After Completion**:
   Always review completed tasks from senior engineering review after completion via Pro or Opus depending on limit remaining or mathematical planner:
   - If we have enough quota left for further reviewing or planning, use Opus (`claude-opus-4-6-thinking`).
   - Else, use Pro on high mode (`gemini-3.1-pro-high`) invoked via `agy` CLI.

2. **Clean Task Lifecycle**:
   Always clean up and kill unwanted or no longer in-use background tasks (like lingering `tail -f`, sleep loops, or temporary monitor tasks) using `manage_task` before stopping or completing things so no dangling tasks are left running.

3. **Multi-Agent SDLC & Graph Integration**:
   - Maintain workspace clean: every test script must be under `testscript/` directory.
   - Code review graph MCP must be consulted for context to prevent token waste and preserve architectural integrity.
   - Every terminal command or curl command must have a clear commented explanation string describing what it achieves.
