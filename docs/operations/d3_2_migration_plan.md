# D3-2 Migration Plan

## Context
- Remote public schema was observed empty at audit time.
- Data-loss risk is low, not zero. Recheck immediately before migration.

## Execution Rules
- Migration runs ONLY through founder-approved operator/CI command.
- Alpha Mac worker and Render runtime MUST NOT automatically execute migration.
- NO migration during service startup.

## Preflight
- Recheck that remote public schema is still empty.
- Capture schema-only preflight evidence before execution.

## Verification (Post-Migration)
- Exact `alembic_version` equals `58b5b056d9e3`.
- Expected core tables exist.
- Required foreign keys and unique constraints exist.
- Application readiness passes.
- No SQLite fallback is occurring.
- No secrets in logs.

## Rollback Policy
- Downgrade base is destructive and requires a separate rollback decision.
- A failed transactional migration should first be inspected, NOT blindly downgraded.
