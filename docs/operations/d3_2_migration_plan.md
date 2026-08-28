# D3-2 Migration Plan

## Scope and Context
- **Project Ref**: `dbiqnilvgcnbqxtgodgo`
- **Observation Timestamp**: `2026-08-28T20:39:00+05:30`
- **Observed Current Revision**: `base/no migration rows`
- **Target Revision**: `58b5b056d9e3`
- **WARNING**: Remote public table-stats was empty at audit time. Data-loss risk is low but not zero. Recheck immediately before migration.
- **Production Safety**: Explicit statement that production remains untouched by this staging migration plan.

## Execution Rules & Authorization
- **Operator Ownership**: Migration runs ONLY through an authenticated operator. NEVER a worker or startup auto-migration.
- **Explicit Authorization**: The exact founder approval string MUST be provided (Do NOT execute this approval, this is for the plan only):
  Approve AlphaBrain staging Supabase migration from base to 58b5b056d9e3 for project dbiqnilvgcnbqxtgodgo.

## Preflight
Secure environment setup (no embedded credentials):
```bash
# Verify credentials are provided via secure environment variable sourcing without hardcoding secrets
export DATABASE_URL="${DATABASE_URL_STAGING}"
```

Exact preflight commands:
```bash
# Check current schema head and confirm the remote public schema is empty
alembic current
```

## Migration Execution
Exact forward migration command:
```bash
# Upgrade DB schema to exactly target head 58b5b056d9e3
alembic upgrade 58b5b056d9e3
```

## Verification (Post-Migration)
Verification SQL to confirm `alembic_version`, expected tables, foreign keys, unique constraints, critical indexes, and zero unexpected multiple Alembic heads:
```sql
-- Verify exact alembic_version (expect exactly 1 row matching 58b5b056d9e3)
SELECT version_num FROM alembic_version;

-- Verify expected core tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Verify foreign keys exist
SELECT conname, contype FROM pg_constraint WHERE contype = 'f';

-- Verify unique constraints exist
SELECT conname, contype FROM pg_constraint WHERE contype = 'u';

-- Verify critical indexes exist
SELECT indexname FROM pg_indexes WHERE schemaname = 'public';
```

Readiness smoke command after migration:
```bash
# Smoke test readiness endpoint, expecting HTTP 200 without exposing secrets
curl -s -o /dev/null -w "%{http_code}" https://<STAGING_HOST>/health/ready
```

**Evidence Destination**:
Sanitized evidence MUST be collected and stored under the ignored directory: `testscript/evidence/`

## Rollback Policy
- **Failure Classification**: Distinguish between transient errors (e.g., connection timeout) vs. logical errors (constraint failure, missing dependencies).
- **No Blind Downgrade**: A failed transactional migration should first be inspected, NOT blindly downgraded.
- **Rollback Decision Matrix**:
  - Connection timeout -> Retry safe.
  - Constraint failure -> Stop and audit schema state. Do not retry without manual intervention.
  - Missing dependent object -> Stop. Review Alembic migration script for gaps.
- **Destructive Action Protection**: Separate founder approval required before any destructive downgrade to base.
