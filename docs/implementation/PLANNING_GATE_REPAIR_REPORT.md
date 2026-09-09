# Planning gate repair and safe resumption

Status: local repair verified; not a new live autonomous-development proof.
Baseline: `c8c5f65`. No commit, push, deployment or live queue mutation performed by this repair.

## Reproduced failures

- Full baseline: **51 failed, 809 passed, 11 skipped**.
- Legacy queue tests approved tasks without planning evidence; another worker fixture attached fabricated, unsigned planning records.
- Approval trusted the mere presence of an attestation. Leasing could proceed when planning records were missing. Neither boundary consistently checked signature, expiration or request identity.
- Attestation signatures omitted reviewer identities, findings, roles and policy metadata.
- Planner read objective/project/repository from top-level task fields, while the queue stores them under `envelope`.
- AGY's `structured_output` wrapper was interpreted as the plan itself; empty drafts could reach critique.
- There was no supported planning CLI entry point, encouraging scratch scripts and direct database writes.
- Worker invocation had regained `--dangerously-skip-permissions`, broad MCP permission grants and raw prompt debugging.

## Repairs

1. Shared validation on attachment, approval and every lease attempt. Verify complete signature, expiry, reviewer separation/roles/verdicts, task/project/repository/base binding, blueprint digest, complete request digest and exact file scope.
2. Sign all serialized attestation fields except the signature itself. Expiry bounded to seven days. Unknown signing keys fail closed. The default key can use configured `ALPHA_SIGNING_SECRET`; no hardcoded secret fallback.
3. Attach plans only to pending tasks. Missing/stale/corrupt plans never acquire an execution lease. Do not alter existing approved task records to make them pass.
4. Parse exactly one AGY JSON document, extracting `structured_output` and rejecting duplicate keys, trailing content, error responses and malformed payloads. Reject empty drafts or changed file scope before critique. Read real nested task metadata and verify research/request binding before model calls.
5. Planning uses sandbox/plan mode, high effort for Gemini and does not pass AlphaBrain signing/service environment credentials to the model subprocess.
6. Added `senior-plan TASK_ID --snapshot PATH`. It generates and attaches the model-reviewed plan but does not approve execution. Failures leave the request and approval state unchanged. Missing planning evidence gives a controlled CLI/safety response rather than a traceback.
7. Removed worker permission-bypass flag, wildcard MCP grants and raw prompt-debug output. Kept containment hooks. Narrowed Python mimetypes compatibility to the public mime.types files instead of all `/etc`.
8. Migrated lifecycle tests to explicit, genuinely signed **test-only** planning fixtures against temporary databases. No production test-mode exemption, global approval monkeypatch, disabled security gate or new skip marker.

## Verification

- Full suite: **901 passed, 11 skipped, 3 warnings**, 67.60 seconds.
- `ruff check .`: passed.
- `ruff format --check .`: 267 files formatted.
- `mypy alpha_core alpha_protocol alpha_worker`: passed, 88 source files.
- `git diff --check`: passed.
- Planning regression coverage: tampered reviewer fields/signature/identity, altered request/blueprint, missing evidence, expired evidence at lease, plan replacement after approval, stale research, malformed AGY output, rejected/failed model calls and CLI state preservation.
- Real macOS sandbox tests pass, including attempted outside writes/reads, shell substitutions, protected-hook changes and symlink escape.
- Worker test state and Fernet key were disposable. Existing 11 skipped tests are not evidence of their associated capabilities; no skip rules were added.

## How Antigravity should resume

The transcript's `tsk_eva_017b7e39c25a` was manually modified and supplied mock planning evidence. Preserve its audit trail; do not treat it as a successful proof or force its status forward. Old partial-field signatures intentionally no longer verify; use a fresh reviewed plan, not an automatic re-signing migration.

1. Independently review this local repair, including the test-only fixture migration. Capture an immutable baseline through the normal authorized workflow.
2. Admit a fresh bounded task using supported commands. Retain exact base SHA, original request, scope and executable gates. Do not strip pytest or independent-review requirements.
3. Gather real research/context and save a `ResearchSnapshot` JSON under `testscript/evidence/`. Required fields: `task_id`, `project_id`, `repository_identity`, exact 40-character `base_sha`, `request_digest`, `retrieval_time`; include actual `sources` and unresolved questions. Compute request digest with `alpha_protocol.planning.request_digest` from the unchanged admitted envelope. Do not fabricate research or reviewer approval.
4. Configure the signing key securely through the normal runtime environment, never in chat, source code or command arguments.
5. Run the supported planning command:

   ```sh
   # Generate model-reviewed planning evidence; does not authorize execution.
   .venv/bin/python -m alpha_core.triage_cli senior-plan TASK_ID \
     --snapshot testscript/evidence/RESEARCH_SNAPSHOT.json
   ```

6. Inspect the resulting plan and obtain the required founder authorization through the normal workflow. Then dispatch the worker, run all required gates, independently review the exact result and obtain promotion approval. Do not manually update task status, retries, gate results, hashes or review records.
7. If blocked: report the exact boundary and preserve evidence. Missing planning needs a new valid plan; changed scope needs new authorization; missing MCP capability needs a scoped adapter repair—not wildcard permissions.

## Explicit remaining boundaries

- This repair does not claim live Pro/Opus consensus, tool-hook compatibility or a new task-to-promotion cycle was proven end to end. Unit model doubles are identified as such.
- Graph MCP was unavailable to this supervisor. No live graph capability is claimed. Generic MCP tools without a containment policy remain denied, intentionally.
- The research broker still needs separate hardening: redirect destination validation occurs after requests; DNS resolution is not pinned; graph freshness currently checks Git HEAD rather than an actual graph snapshot; capability detection is hardcoded. Its existing tests are not production SSRF or graph-freshness proof. Do not use it to fetch untrusted research URLs until that packet is independently verified.
- Signatures prove origin/integrity under the configured service key, not the semantic correctness of model reasoning. Protect signing credentials from execution workers; this change is not an operating-system isolation audit of all planning/review processes.
- SQLAlchemy core tasks and the SQLite triage queue are distinct execution paths. These new queue checks do not by themselves prove identical planning enforcement throughout every other admission path.

Next bounded packet: safe research capability/transport verification, then a fresh approved end-to-end planning → execution → independent review → promotion proof. Never declare the whole system "zero defect" from this suite.
