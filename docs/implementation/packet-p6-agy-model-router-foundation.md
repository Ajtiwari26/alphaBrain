# Packet P6-R1 — AGY Model Router Foundation

**Supervisor:** Codex senior engineer  
**Executor:** AGY using `gemini-3.1-pro-high`, effort `high`  
**Risk:** medium because shared authentication exists  
**Production/cloud side effects:** forbidden

## Objective

Create reusable AGY skill and deterministic local model/account planner described by
`docs/architecture/agy-model-account-routing-audit.md`. This phase selects and records decisions;
it must not change active account, invoke model requests, or integrate with AlphaBrain runtime yet.

## Read first

- `docs/architecture/agy-model-account-routing-audit.md`
- `/Users/ajaytiwari/.gemini/config/skills/switch-account/SKILL.md`
- `/Users/ajaytiwari/.local/bin/agy-switch` (read-only)
- `/Users/ajaytiwari/.gemini/config/skills/multi-agent-sdlc/SKILL.md`

## Allowed files

- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/SKILL.md`
- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/references/routing-policy.md`
- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/scripts/model_router.py`
- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/testscript/test_model_router.py`
- `docs/implementation/packet-p6-agy-model-router-foundation.md` only if factual execution notes are
  needed

Do not modify AlphaBrain Python runtime, current D1 files, existing skills, `agy-switch`, profiles,
tokens, Keychain, `.env*`, account pointer, or any other file.

## Required behavior

### Skill

- Concise discovery description for AlphaBrain task-to-model and account selection.
- Route detailed matrix to `references/routing-policy.md` through progressive disclosure.
- Explicitly say supervisor packet is authority and model choice cannot waive gates/approvals.
- Distinguish planning, implementation, review, QA, and mechanical stages.
- State exact AGY model IDs currently verified by `agy models`.

### Selector CLI

Implement Python standard-library-only CLI with explicit state path override for tests:

- `catalog`: emit supported policy profiles as JSON without calling AGY.
- `select --request <json-file> --state <json-file>`: emit deterministic JSON selection containing
  model, effort, account, rationale codes, independence status, and fallback chain.
- `record --state <json-file> --event <json-file>`: atomically update non-secret ledger from
  sanitized success, rate limit, auth failure, or manual availability event.
- `status --state <json-file>`: emit redacted ledger summary.

No `run`, `switch`, Keychain, token, network, or AGY subprocess command in this phase.

### Deterministic policy

- Critical plan: Opus 4.6 Thinking, one bounded plan turn policy.
- Independent review: Sonnet 4.6; never report independent family when same provider/model family.
- Nontrivial implementation: Gemini 3.1 Pro High initially.
- Fast/mechanical/QA: Gemini 3.7 Flash High.
- Exact allowed models only. Unknown model/account/state input fails closed.
- Prefer eligible account with oldest `last_selected_at`; deterministic account-ID tie-break.
- Skip cooldown/auth-failed/disabled profiles.
- Use provider reset timestamp when present. Otherwise rate-limit record uses configurable five-hour
  fallback and labels source `configured_fallback`.
- No eligible account returns structured `rate_limited` decision with earliest known retry, not a
  hidden fallback.
- Claude unavailable: follow declared fallback but mark reviewer independence degraded when needed.
- One routing decision does not mutate ledger. Only `record` mutates.
- Atomic ledger write uses temporary sibling plus replace; permissions must not become broader than
  owner read/write.
- Ledger rejects or redacts token-like keys/values and raw provider payloads.

## Required tests

Use temporary directories and fake account IDs only. Prove:

1. every stage selects expected model and effort;
2. account selection is deterministic and least-recently-selected;
3. cooldown, auth-failed, and disabled accounts are skipped;
4. explicit reset beats fallback; absent reset produces five-hour inferred cooldown;
5. exhausted pool returns truthful rate-limited decision;
6. review independence and degraded fallback are correct;
7. unknown models/stages/states fail closed;
8. selection is read-only; record writes atomically;
9. ledger contains no token/secret/raw-response fields and file mode is owner-only;
10. no subprocess, network, Keychain, profile, or active-account mutation occurs.

## Gates

```bash
# Validate skill metadata and unfinished placeholders.
python3 /Users/ajaytiwari/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router

# Run focused selector and ledger tests.
python3 -m unittest discover -s /Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/testscript -p 'test_*.py' -v

# Compile deterministic router script.
python3 -m py_compile /Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/scripts/model_router.py
```

Also inspect changed-file boundary and run secret-pattern scan against new skill directory. Do not
run repository-wide formatter or tests because runtime is untouched.

## Stop condition

Return `ALPHA_BRAIN_TASK_DONE` only when all gates pass and changed files equal allowlist. Otherwise
return `ALPHA_BRAIN_TASK_BLOCKED` with exact evidence. Never deploy, push, commit, switch account,
or continue into runtime integration.
