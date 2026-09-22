#!/usr/bin/env python3
"""
Test which saved accounts have a valid Google Cloud Code license.
"""

import json
import urllib.request
from pathlib import Path

CLIENT_ID = "os.environ.get("GOOGLE_CLIENT_ID", "")"
CLIENT_SECRET = "os.environ.get("GOOGLE_CLIENT_SECRET", "")"

def refresh_token(token_data):
    import urllib.parse
    tok = token_data.get("token", {})
    refresh_tok = tok.get("refresh_token")
    if not refresh_tok:
        return token_data.get("access_token")

    body = urllib.parse.urlencode({
        "refresh_token": refresh_tok,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
    }).encode()

    try:
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
        with urllib.request.urlopen(req, timeout=8) as resp:
            res = json.loads(resp.read().decode())
        new_access = res.get("access_token")
        if new_access:
            tok["access_token"] = new_access
            token_data["token"] = tok
            return new_access
    except Exception as e:
        print(f"Refresh failed: {e}")
    return tok.get("access_token")

def test_accounts():
    profiles_dir = Path.home() / ".gemini" / "profiles"
    accounts = [p.name for p in profiles_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    url = "https://daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse"

    payload = {
        "project": "aicode-consumers",
        "model": "gemini-2.5-flash",
        "requestId": "ping-test",
        "request": {
            "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
        }
    }

    valid_licensed_accounts = []

    for acc in sorted(accounts):
        token_file = profiles_dir / acc / "jetski-standalone-oauth-token"
        if not token_file.exists():
            print(f"[{acc}] No token file")
            continue

        try:
            data = json.loads(token_file.read_text())
            token = refresh_token(data)
            if not token:
                print(f"[{acc}] No access token in file")
                continue
            # Save refreshed token
            token_file.write_text(json.dumps(data, indent=2))

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "User-Agent": "antigravity/1.107.0 darwin/arm64",
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"[{acc}] ✅ HTTP {resp.status} (LICENSED & ACTIVE!)")
                valid_licensed_accounts.append(acc)
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            if "SUBSCRIPTION_REQUIRED" in err:
                print(f"[{acc}] ❌ 403 SUBSCRIPTION_REQUIRED")
            elif "429" in str(e.code) or "RESOURCE_EXHAUSTED" in err:
                print(f"[{acc}] ⚠️ 429 Quota Exhausted")
            else:
                print(f"[{acc}] ❌ {e.code}: {err[:80]}")
        except Exception as e:
            print(f"[{acc}] ❌ Error: {e}")

    print("\nSummary of valid licensed accounts:", valid_licensed_accounts)
    return valid_licensed_accounts

if __name__ == "__main__":
    test_accounts()
