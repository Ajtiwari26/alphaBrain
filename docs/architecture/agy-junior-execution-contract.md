# AlphaBrain Junior Execution Contract
**Version**: 1

This contract strictly defines the execution boundaries and protocols for any junior agent (AGY) accepting tasks from the AlphaBrain supervisor daemon. The contract is absolute and executable.

## 1. Immutable Inputs
The task begins with a rigidly bounded context. The junior must adhere to:
- **Task ID & Project ID**
- **Worktree Location**
- **Base Commit**
- **Allowed Paths**
- **Allowed Tools**
- **Risk Class**
- **Accepted Gate Commands**

## 2. Phase 0: Orientation
Before acting, the junior must validate the scope against the immutable inputs. It must produce a plan of maximum five lines. Any deviation requires immediate blockage.

## 3. Pre-edit Graph Checks
The junior must utilize the `code-review-graph` MCP server to construct its knowledge context:
1. `build_or_update_graph_tool`
2. `get_review_context_tool`
The tool schema must be explicitly respected.

## 4. Bounded Implementation
The junior is strictly restricted to modifying files within the `allowed_paths`. Modifying code outside these paths is a severe contract violation.

## 5. Execution of Acceptance Commands
The junior must run the exact declared acceptance commands.
- It must capture the exit code and terminal output.
- It must *never* substitute a different command for an assigned gate.
- If the task is user-facing, it must additionally run browser/E2E tests, keyboard navigation checks, and responsive design checks as evidence.

## 6. Post-edit Graph Checks & Review
The junior must rerun the code-review graph tools after edits to detect and fix any material findings or architectural regressions before completing the task.

## 7. QA Manifest
The junior must produce a single-line JSON manifest before termination. Schema:
- `contract_version`: 1
- `project_id`: str
- `task_id`: str
- `executed_commands`: list of objects `{command, exit_code, summary}`
- `required_gates`: list of strings
- `passed_gates`: list of strings
- `review_calls`: int
- `security_review`: dict or bool
- `artifacts`: list of paths
- `blockers`: list of strings

## 8. Terminal Protocol
- **Success**: Only after *every* required gate command passes (exit code 0), emit exactly `ALPHA_BRAIN_TASK_DONE` on its own line.
- **Failure**: On any blocked, failing gate, or missing evidence, emit `ALPHA_BRAIN_TASK_BLOCKED: <exact reason>` and NEVER emit the success token.

## 9. Explicit Anti-patterns
- NO claiming tests pass without actual captured command output.
- NO silent permission denial (must loudly fail/block).
- NO self-approval, deployments, or remote push commands.
- NO production side effects or database mutation outside local sqlite/test bounds.
- NO execution of unauthorized external network fetches or dependency installation commands (`npm install`, `npm ci`, `npx playwright install`, `curl`, `wget`) unless explicitly granted by a future policy exception (Deferred: future Dependency Acquisition Policy needs a founder-approved immutable package/lockfile/network contract; not implemented now).
- NO roadmap changes or broader refactoring beyond task objective.
- NO invented fallback models or identity shifting.

## 10. Retry Rule
The junior is an ephemeral function. The supervisor assumes complete control over retry logic. The junior must fail immediately upon an unrecoverable state so the supervisor can record failure evidence and construct a narrow repair task. The junior must never rerun uncontrolled retry loops internally.


### Browser Evidence Policy
Browser smoke evidence is strictly conditional on explicit declaration via `AcceptancePlan.browser_smoke_url`. If not declared, the agent MUST NOT attempt browser-driver download or installation. Future fully browser-tested projects will require preprovisioned local browser environments rather than ad-hoc runtime acquisition.

### Gate Evidence Persistence
All gate evidence items submitted within the QA Manifest (whether the task is verified or retryable-failed) are durably recorded as individual `GateEvidenceRecord` rows mapped to the specific attempt, ensuring auditability of each individual check.
