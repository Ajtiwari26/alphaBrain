# Alpha Brain

Alpha Brain coordinates DeployMate work across Unifold, AgentLine, Inito, and local
development workers. Current verified vertical slice is Unifold Meet: founder joins a
LiveKit room, Eva joins as a participant, and Gemini Live provides duplex voice plus
live transcription.

## Verified meeting flow

- Founder authentication through Alpha API bearer token.
- One-hour signed client invite links without exposing founder token.
- LiveKit microphone, camera, remote audio/video, chat, reconnect, end call, and screen
  share controls.
- Eva room participant backed by Vertex AI Gemini Live native audio with Aoede voice.
- Active-speaker switching for founder/client while retaining one room-scoped Gemini
  context.
- Input/output transcription using LiveKit legacy events and `lk.transcription` streams.
- Narrow-screen transcript drawer.

## Local setup

Python 3.11+ and LiveKit Server are required. macOS Homebrew can install LiveKit.

```bash
# Create isolated Python runtime and install Alpha Brain dependencies.
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Install local LiveKit SFU on macOS.
brew install livekit
```

Copy `.env.example` to `.env.local`, replace every placeholder, and configure one
Gemini provider:

- Vertex AI: set `GEMINI_USE_VERTEX=true`, Google project/location, and service-account
  credential path.
- Gemini Developer API: set `GEMINI_USE_VERTEX=false` and `GOOGLE_API_KEY`.

For Gemini Developer API meetings, use
`GEMINI_LIVE_MODEL=gemini-2.5-flash-native-audio-latest`. Gemini 3.1 Live currently
connects directly but is not compatible with Alpha Brain's LiveKit realtime-agent
configuration, so it must not be used for Eva rooms.

Never commit `.env.local` or reuse sample keys in production.
Rotate any credential that was ever pasted into source, logs, screenshots, or chat.

```bash
# Start local LiveKit with same key and 32+ character secret configured in .env.local.
livekit-server --bind 127.0.0.1 --node-ip 127.0.0.1 --keys $'YOUR_KEY: YOUR_32_BYTE_SECRET\n'

# Start Alpha Brain API and meeting site.
./.venv/bin/uvicorn alpha_core.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/meet`, enter founder API token, then join. Use invite button
to create a client-only signed link.

## Verification

```bash
# Run complete deterministic regression suite.
./.venv/bin/pytest -q

# Prove LiveKit text input returns Gemini transcript plus voiced PCM audio.
ALPHA_API_TOKEN='YOUR_LOCAL_API_TOKEN' ./.venv/bin/python testscript/smoke_livekit_eva.py

# Prove direct Gemini Live provider audio and transcription.
./.venv/bin/python testscript/smoke_gemini_live.py
```

## Antigravity worker

Alpha Brain currently executes development tasks through Antigravity only. Claude Code, Codex,
and Gemini worker envelopes are rejected rather than silently routed elsewhere.

No Antigravity window needs opening. Alpha Brain uses official `agy` CLI headless mode from the
client worktree. First task runs with `--new-project`; Alpha Brain stores only returned
conversation ID and exact repository path in Memory Graph. Later tasks use `--conversation` for
that ID. The bridge never reads IDE databases, scans active IDE processes, or borrows arbitrary
chats. It parses AGY NDJSON tool events and terminal result, then rejects completion unless
code-review graph calls and multi-agent-sdlc QA evidence are present.
After an implementation turn passes, Alpha Brain sends a mandatory second QA-audit turn in the
same conversation. Antigravity must independently reproduce flows, repair defects itself, rerun
gates, and return audit evidence before Alpha Brain accepts completion.

AGY headless command permissions are policy-controlled. File reads/writes in the active worktree
are permitted by AGY defaults, but test/build commands need narrowly scoped rules in
`~/.gemini/antigravity-cli/settings.json`; Alpha Brain never passes
`--dangerously-skip-permissions`.

```bash
# Run isolated calculator task through official AGY CLI.
./.venv/bin/python testscript/run_antigravity_calculator_task.py --port 4173
```

## P5 background Mac worker

Production execution is outbound-only: worker registers with control plane, sends health and
heartbeats, leases one task, then submits one idempotent result. It never opens Chrome, an IDE,
or meeting UI. Network loss writes encrypted events under `WORKER_STATE_DIR/spool`; replay occurs
before fresh health after reconnect. Worker only creates worktrees from clean source at exact
resolved base commit, refuses dirty cleanup, preserves task branches, and runs only AGY.

Set `ENV=production`, `WORKER_CONTROL_PLANE_URL`, `WORKER_USE_KEYCHAIN=true`, and
`WORKER_ALLOW_LOCAL_DB=false`. Store secrets in macOS Keychain service
`com.deploymate.alphabrain`: `worker-token`, `worker-identity`, `worker-spool-fernet-key`.
Never put production values in `.env.local`.

AlphaBrain requires Postgres for production task state, leases, audit history, and recovery.
Supabase Postgres is compatible: use its session-pooler `postgresql://` URL on port 5432; Alpha
Brain maps it to async psycopg automatically. Free Supabase is suitable for staging only because
free projects can pause after inactivity and have a 500 MB database quota. Use paid Supabase or
Render Postgres for production durability and backups. Redis is not required by current code;
Upstash Redis can be added later for high-volume queue/cache workloads.

```bash
# Run worker after Keychain and production settings are configured.
./.venv/bin/python -m alpha_worker run

# Stop new leases persistently, then resume and inspect local state.
./.venv/bin/python -m alpha_worker pause --reason maintenance
./.venv/bin/python -m alpha_worker resume
./.venv/bin/python -m alpha_worker status
```

Supported mode: lid open, AC power, screen locked/off. Closed-lid work requires macOS-supported
clamshell hardware with external power/display; it cannot wake powered-off Mac. Inito camera
owner detection needs external camera when display is closed. Enable FileVault, use dedicated
non-admin macOS worker account, then install launchd template after staging validation.

Install only from that dedicated account after exporting production settings and storing Keychain
secrets; installer refuses development/local-DB mode:

```bash
# Install, validate, and kickstart this worker's per-user launchd service.
./ops/launchd/install_worker.sh /Users/ajaytiwari/Desktop/Projects/alphaBrain

# Unload service while retaining prior plist for recovery inspection.
./ops/launchd/uninstall_worker.sh
```

## Remaining production gates

- Deploy LiveKit behind TLS with TURN and test founder/client on separate networks.
- Add recording/transcription consent, retention, export, and deletion controls.
- Persist room transcripts and derived specifications separately.
- Add role/tenant authorization, room lock, participant removal, and rate limiting.
- Test real remote screen share, interruption/reconnect, simultaneous rooms, and second
  device media end-to-end.
- Replace private RoomIO participant switching when LiveKit exposes a public shared-room
  multi-participant input API.

See [TODO.md](TODO.md) for complete roadmap and acceptance gates.
