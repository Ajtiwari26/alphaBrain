# Alpha Brain Production Deployment: Render & Supabase

This document details the manual setup, configuration, verification, and rollback procedures for deploying the Alpha Brain control plane on a **Render Web Service** connected to a **Supabase PostgreSQL** database.

---

## Architecture Overview

1. **Render Web Service (`alpha-brain`)**: Runs the FastAPI application ([`alpha_core.api.app:app`](file:///Users/ajaytiwari/Desktop/Projects/alphaBrain/alpha_core/api/app.py)), exposing health endpoints, LiveKit token generation, task ingestion, and worker coordination endpoints.
2. **Supabase PostgreSQL**: Acts as the durable system of record for tasks, worker registrations, health history, meeting state, and audit records.
3. **Local Mac Execution Worker (P5)**: Connects outbound to the Render control plane via HTTPS; no direct database connection or inbound open ports are needed on the worker machine.
4. **No-Redis-Required Architecture**: Alpha Brain uses PostgreSQL transaction-safe leasing with `FOR UPDATE SKIP LOCKED` and lightweight in-memory caching. A Redis/Upstash instance is **not required** for core operations.

---

## 1. Supabase PostgreSQL Configuration

### 1.1 Database Provisioning
1. In the [Supabase Dashboard](https://supabase.com/dashboard), create a new project (e.g., in region `singapore` to co-locate with the Render service).
2. Set a strong database password and save it in a secure password manager.

### 1.2 Connection String (Session Pooler)
1. Navigate to **Project Settings** > **Database** > **Connection Pooling**.
2. Copy the **Session Pooler** URI (port `5432`):
   ```text
   postgresql://postgres.[YOUR-PROJECT-REF]:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```
3. *Note*: Alpha Brain automatically translates standard `postgresql://` connection strings to SQLAlchemy async `postgresql+psycopg://` drivers at startup in [`alpha_core/db/connection.py`](file:///Users/ajaytiwari/Desktop/Projects/alphaBrain/alpha_core/db/connection.py).

---

## 2. Render Web Service Deployment

> [!WARNING]
> **Render Free Plan Operational Boundary**: Render Free web services spin down after periods of inactivity (cold starts). As a result, the Free plan is suitable for preview, development, and control-plane smoke testing only. It cannot meet Alpha Brain P5 24x7 worker-orchestration leasing loops or immediate voice/telephony call reliability requirements. Upgrading to a paid, always-on instance remains a mandatory production gate.

### 2.1 Deploying via Blueprint (`render.yaml`)
1. In the [Render Dashboard](https://dashboard.render.com), click **New** > **Blueprint**.
2. Connect the `alphaBrain` repository.
3. Render will detect [`render.yaml`](file:///Users/ajaytiwari/Desktop/Projects/alphaBrain/render.yaml) and configure the `alpha-brain` Python Web Service on the `free` plan in region `singapore`.

### 2.2 Manual Configuration (Alternative)
If creating the service manually without Blueprint:
- **Service Type**: Web Service
- **Runtime**: Python 3.11+
- **Plan**: Free
- **Region**: Singapore (`singapore`)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn alpha_core.api.app:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`
- **Auto-Deploy**: Yes (on push to `main`)

### 2.3 Required Environment Variables

#### Non-Secret Variables (Preconfigured in `render.yaml`)
| Variable | Value | Purpose |
|---|---|---|
| `ENV` | `production` | Production environment flag |
| `DEBUG` | `false` | Disables verbose debug and auto-reload |
| `GEMINI_USE_VERTEX` | `false` | Use Developer API or Vertex AI |
| `GEMINI_LIVE_MODEL` | `gemini-2.5-flash-native-audio-latest` | Model for Eva meeting audio |
| `GEMINI_LIVE_VOICE` | `Aoede` | Eva synthesized voice persona |
| `ALLOWED_GATE_EXECUTABLES` | `pytest,ruff,mypy,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go` | Permitted gate binaries |
| `WORKER_ALLOW_LOCAL_DB`| `false` | Disallows SQLite development fallback |
| `ANTIGRAVITY_EXECUTION_ENABLED`| `false` | Disables local Mac AGY runs on Render |

#### Required Manual / Secret Configuration (Configure in Render Dashboard)
| Variable | Description |
|---|---|
| `PUBLIC_BASE_URL` | Canonical public URL of your Render service (e.g., `https://<your-service-name>.onrender.com`) |
| `CORS_ORIGINS` | Allowed origins matching your deployed domain (e.g., `https://<your-service-name>.onrender.com`) |
| `DATABASE_URL` | Supabase Postgres Session Pooler URI (port `5432`) |
| `ALPHA_API_TOKEN` | 32+ character random secret for founder/admin API authentication |
| `ALPHA_WORKER_TOKEN` | 32+ character random secret for Mac worker authentication |
| `ALPHA_SIGNING_SECRET` | 32+ character random secret for stream tokens and webhook nonces |
| `GEMINI_API_KEY` | Google AI Studio or Vertex API key |
| `LIVEKIT_URL` | LiveKit Server / Cloud WebSockets URL (`wss://...`) |
| `LIVEKIT_API_KEY` | LiveKit API Key |
| `LIVEKIT_API_SECRET` | LiveKit API Secret (32+ characters) |
| `PLIVO_AUTH_ID` | (Optional) Plivo Account Auth ID |
| `PLIVO_AUTH_TOKEN` | (Optional) Plivo Auth Token |
| `PLIVO_PHONE_NUMBER` | (Optional) Plivo Phone Number |

---

## 3. Database Schema Initialization & Migrations

### 3.1 Initial Table Creation
Alpha Brain's FastAPI lifespan automatically invokes `init_db()` upon boot in [`alpha_core/api/app.py`](file:///Users/ajaytiwari/Desktop/Projects/alphaBrain/alpha_core/api/app.py), creating all required SQLAlchemy models:
- `tasks`, `attempts`, `task_dependencies`, `task_approvals`
- `workers`, `worker_health`
- `meetings`, `meeting_participants`, `meeting_events`, `meeting_transcripts`
- `specifications`
- `call_jobs`, `audit_events`

### 3.2 Manual Migration Check (Alembic)
If schema migrations are tracked via Alembic:
```bash
# Apply all pending Alembic schema migrations to target Supabase database
DATABASE_URL="postgresql://..." alembic upgrade head
```

---

## 4. Verification & Health Checks

Once the Render service status turns **Live**:

### 4.1 Public Health Endpoint
```bash
# Query public health endpoint to verify control-plane boot status
curl -f https://<your-service-name>.onrender.com/health
```
**Expected Response (HTTP 200)**:
```json
{
  "status": "healthy",
  "app": "Alpha Brain",
  "env": "production"
}
```

### 4.2 Authenticated Worker Health Reporting
Verify that unauthenticated worker registration is rejected with HTTP `401 Unauthorized` when sending a valid registration payload:
```bash
# Verify that unauthenticated worker registration fails closed with HTTP 401 Unauthorized
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://<your-service-name>.onrender.com/api/workers/register \
  -H "Content-Type: application/json" \
  -d '{"worker_id":"test-worker","hostname":"test-host","platform":"darwin","agent_types":["antigravity"],"capabilities":{"supported_agents":["antigravity"],"gpu_available":false,"tools":[]}}'
# Expected output: 401
```

### 4.3 Meeting Token Generation
Verify authenticated LiveKit token minting:
```bash
# Request signed LiveKit token with valid founder authorization header
curl -X POST https://<your-service-name>.onrender.com/api/meet/token \
  -H "Authorization: Bearer <ALPHA_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"room_name": "prod-smoke-test", "identity": "Ajay (Founder)"}'
```
**Expected Response (HTTP 200)** with signed `token` and `livekit_url`.

---

## 5. Backup & Rollback Procedures

### 5.1 Free-Tier Supabase Backup Limitations
- **No Automatic Backups / PITR**: Supabase Free projects do not include automated daily backups or Point-In-Time Recovery (PITR).
- **Operator-Managed Logical Backups**: Before applying significant schema migrations or data alterations, operators must take a manual logical dump:
  ```bash
  # Export manual timestamped logical SQL dump of Supabase database before migrations
  pg_dump "postgresql://postgres.[REF]:[PASS]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres" > alphabrain_backup_$(date +%Y%m%d_%H%M%S).sql
  ```
- **Database Restore Availability**: Database restore is unavailable unless an operator possesses a verified manual logical backup, or upgrades to a paid Supabase plan with PITR enabled.

### 5.2 Application & Schema Rollback
1. **Render Web Service Rollback**:
   - In the Render Dashboard, navigate to **Deployments**.
   - Select the previous functional deployment and click **Rollback to this deploy**.
2. **Schema Rollback Considerations**:
   - Rolling back the web service deployment only restores application binaries; it does not alter or revert database state.
   - If a breaking schema change was applied, run Alembic downgrade scripts or restore from the manual logical dump before rolling back application code:
     ```bash
     # Roll back the most recent database migration
     alembic downgrade -1
     ```
