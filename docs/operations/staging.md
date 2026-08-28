# Staging Environment Operations

The staging environment is an isolated replica of production used for validating configuration hardening and release candidates before deploying to production.

## Configuration Requirements

When provisioning the staging environment on Render, ensure the following environment variables are strictly configured to simulate production:

- `ENV`: Must be `staging` to trigger staging-specific safety validations.
- `DEBUG`: Must be `false`.
- `DATABASE_URL`: Must point to a valid PostgreSQL instance (SQLite is rejected).
- `WORKER_ALLOW_LOCAL_DB`: Must be `false`.
- `ANTIGRAVITY_EXECUTION_ENABLED`: Must be `false` (Render should not execute Antigravity itself).
- `ALPHA_API_TOKEN`, `ALPHA_WORKER_TOKEN`, `ALPHA_SIGNING_SECRET`: Must be exactly 32+ characters long.
- `WORKER_CONTROL_PLANE_URL`: Must not point to `localhost`.

## Verification Steps

1. **Liveness**: Check the `/health/live` endpoint. It will return `{"status": "alive"}` to prove the process event loop is responding.
2. **Readiness**: Check the `/health/ready` endpoint. It will return `{"status": "ready"}` to prove the database connection and migration compatibility. If the database is down, it returns a 503 response without leaking connection secrets.
3. **Database Checks**: The application enforces that SQLite cannot be used and that a valid PostgreSQL connection is provided.

## Rollback

If validation fails in staging, revert the configuration or code changes. Staging does not impact production data.
