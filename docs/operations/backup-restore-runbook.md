# Database Backup, Verification, and Rollback Runbook

## Overview
This runbook defines the procedures for logical backup exports, integrity checksum verification, retention lifecycle pruning, and staging migration rollbacks for Alpha Brain.

---

## 1. Logical Export Command
To generate a logical PostgreSQL export with schema and data:

```bash
# Export logical PostgreSQL schema and data to timestamped dump file
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-privileges --file="./backups/alphabrain_$(date +%Y%m%d_%H%M%S).dump"
```

---

## 2. Backup Integrity Verification
Every backup generates a `.manifest.json` recording the SHA-256 checksum and table row counts:

```bash
# Compute SHA-256 checksum of backup dump
shasum -a 256 ./backups/alphabrain_*.dump
```

The checksum is verified against the manifest before any restore operation is attempted.

---

## 3. Database Restore Runbook
To restore a verified logical backup to a clean database:

```bash
# Restore PostgreSQL database from custom format dump
pg_restore --clean --if-exists --no-owner --no-privileges -d "$DATABASE_URL" ./backups/alphabrain_backup.dump
```

---

## 4. Staging Migration Rollback Procedure
Before rolling back migrations in staging:
1. Verify no active task leases or long-running worker operations are in progress.
2. Run Alembic downgrade command to revert the targeted revision:

```bash
# Downgrade database schema by one revision
alembic downgrade -1
```

3. Confirm table structures and constraints with Alembic current:

```bash
# Check current database migration revision
alembic current
```
