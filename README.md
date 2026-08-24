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

Never commit `.env.local` or reuse sample keys in production.

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
