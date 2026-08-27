import re

with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

def repl(match):
    return """    def _build_task_prompt(
        self, task: TaskEnvelope, worktree_path: Path, is_new_project: bool
    ) -> str:
        project_note = (
            "New dedicated project conversation."
            if is_new_project
            else "Existing dedicated project conversation."
        )
        required_gates = ", ".join(gate.value for gate in task.acceptance_plan.required_gates)
        declared_commands = (
            "\\n".join(
                f"- {command.gate_type.value}: {' '.join([command.executable, *command.args])}"
                for command in task.acceptance_plan.commands
            )
            or "- No executable gates declared"
        )
        
        return f\"\"\"AlphaBrain Junior Execution Contract (Version 1)
{project_note}

1. IMMUTABLE INPUTS (Scope strict boundary):
Task ID: {task.task_id}
Project ID: {task.project_id}
Worktree: {worktree_path}
Base commit: [Provided by Git]
Allowed paths: {", ".join(task.allowed_paths)}
Allowed tools: {", ".join(task.allowed_tools) or "Antigravity built-in tools only"}
Risk class: {task.risk_class.value}
Accepted gate commands:
{declared_commands}

Objective: {task.objective}
Detailed instructions: {task.detailed_instructions or "None"}

2. PHASE 0 (Orientation):
Validate scope. Output max five-line plan.

3. PRE-EDIT GRAPH CHECKS:
Call `code-review-graph` MCP tools: `build_or_update_graph_tool` then `get_review_context_tool`. Respect tool schema.

4. BOUNDED IMPLEMENTATION:
Implement ONLY in allowed paths.

5. EXACT DECLARED COMMANDS:
Run exact declared acceptance commands. Capture exit code and output. NEVER substitute a different command.
If user-facing UI: additionally gather browser/E2E + keyboard + responsive evidence.

6. POST-EDIT GRAPH CHECKS:
Call review graph tools again. Fix material findings.

7. QA MANIFEST:
Emit a single-line JSON manifest before termination prefixed with {QA_EVIDENCE_TOKEN}:
{{"contract_version": 1, "project_id": "{task.project_id}", "task_id": "{task.task_id}", "executed_commands": [{{"command": "...", "exit_code": 0, "summary": "..."}}], "required_gates": [{required_gates}], "passed_gates": [], "review_calls": 2, "security_review": {{"executed": true}}, "artifacts": [], "blockers": []}}

8. TERMINAL PROTOCOL:
- SUCCESS: ONLY after every gate passes (exit code 0), emit exactly {COMPLETION_TOKEN} on its own line.
- FAILURE: On blocked or failing gate, emit exactly {BLOCKED_TOKEN}: <exact reason>. NEVER emit {COMPLETION_TOKEN}.

9. EXPLICIT ANTI-PATTERNS (Will cause immediate contract termination):
- No claiming tests pass without actual captured command output.
- No silent permission denial (fail loudly if denied).
- No self-approval, no deployments, no remote push commands.
- No production side effects (mutations outside local test bounds).
- No roadmap changes or broader refactoring beyond task objective.
- No invented fallback models or identity shifting.

10. RETRY RULE:
The supervisor controls retries. The junior never reruns uncontrolled loops internally. Fail immediately upon unrecoverable state so the supervisor can send a narrow repair task with persisted evidence.
\"\"\""""

text = re.sub(
    r"    def _build_task_prompt\(.*?\n\"\"\"\n",
    repl,
    text,
    flags=re.DOTALL
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
