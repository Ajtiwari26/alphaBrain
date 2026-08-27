# Senior Review — P6-R1 AGY Model Router Foundation

**Verdict:** rejected; bounded repair required  
**Implementation conversation:** `0e0cec35-53d6-4aac-9574-b595a0830c5f`

## Policy violation

AGY installed user-level `PyYAML 6.0.3` after `quick_validate.py` reported a missing module. Packet
forbade dependency installation. Do not install or uninstall anything during repair. Validator is
now runnable, but this side effect remains disclosed and P6-R1 cannot be called cleanly executed.

## Required code repairs

1. `select` must reject any account not declared in ledger. Missing per-model state is `unknown`,
   not silently `available`.
2. Validate every ledger account-model state against exact values: `unknown`, `available`,
   `cooldown`, `auth_failed`, `disabled`. Unknown values fail closed.
3. `record` must reject unknown model IDs, unknown account IDs, unknown statuses, malformed state,
   nonnumeric reset values, and provider reset timestamps not later than event time.
4. Request `allowed_models` must be a nonempty subset of exact catalog when supplied and must
   constrain policy candidates. Unknown/empty lists fail closed.
5. Emit structured rationale code list, not prose fallback index.
6. Emit fallback chain as remaining valid candidates after selected model, not already-failed
   predecessors. For `rate_limited`, include earliest retry plus whether timestamp is known.
7. Review request must provide exact `implementation_model`; derive provider family from exact
   catalog. Unknown/missing implementation model fails closed. Only different provider family is
   independent. Same provider family must be `degraded` and include `founder_review_required=true`.
8. `status` must scrub/redact loaded ledger before printing. Never output raw untrusted ledger.
9. Secret scrubbing must recurse through mappings and lists. Remove broad substring rule `"ey"`,
   which redacts ordinary values. Use explicit token patterns and sensitive key names.
10. Preserve event time and reset-source truth. Accept optional numeric `observed_at`; default current
    UTC epoch. Explicit provider reset wins; missing reset creates exactly configurable five-hour
    fallback labeled `configured_fallback`.
11. Atomic write must clean temporary sibling on failure and set final state file mode `0600`.
12. Keep selector standard-library-only and side-effect free except explicit `record` state write.

## Required test repairs

- Replace fake `m1` with exact catalog model IDs.
- Remove duplicate/overwritten dictionary setup.
- Test all five stages.
- Test unknown account, model, state, status, malformed JSON/state, invalid reset, and invalid
  `allowed_models` fail closed.
- Test request model constraint and truthful fallback chain.
- Test exact independent/degraded review behavior for Gemini and Claude implementation models.
- Test `status` redacts nested dict/list secret fixtures without changing source file.
- Patch/guard subprocess, socket/network, and Keychain-like calls so any invocation fails test.
- Test atomic write cleanup, mode `0600`, selection read-only, and deterministic account tie-break.

## Allowed files

- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/SKILL.md`
- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/references/routing-policy.md`
- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/scripts/model_router.py`
- `/Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/testscript/test_model_router.py`

No other edit, dependency action, account action, model call, runtime integration, deployment, commit,
or push.

## Gates

```bash
# Validate skill metadata with already-available validator environment.
python3 /Users/ajaytiwari/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router

# Run focused selector and ledger tests.
python3 -m unittest discover -s /Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/testscript -p 'test_*.py' -v

# Compile router without installing anything.
python3 -m py_compile /Users/ajaytiwari/.gemini/config/skills/alphabrain-model-router/scripts/model_router.py
```

Then list exact files and inspect for forbidden imports/actions. Completion marker remains
`ALPHA_BRAIN_TASK_DONE`; unresolved item requires `ALPHA_BRAIN_TASK_BLOCKED`.
