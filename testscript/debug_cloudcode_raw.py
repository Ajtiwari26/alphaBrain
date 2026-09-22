#!/usr/bin/env python3
import json
import urllib.request
from pathlib import Path


def test():
    home = Path.home()
    token_file = home / ".gemini" / "profiles" / "snapthinktrader@gmail.com" / "jetski-standalone-oauth-token"
    token_data = json.loads(token_file.read_text())
    access_token = token_data["token"]["access_token"]

    url = "https://daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse"

    prompt = (
        "You are an expert autonomous software engineer solving a coding task.\n"
        "Objective: In src/lib.rs, fix the concurrency deadlock and dirty read bugs in MvccEngine by enforcing monotonic lock hierarchy: Rank 1 active_txs, Rank 2 index across methods get, commit, garbage_collect.\n"
        "Turn: 3\n"
        "Solve this task directly and efficiently.\n"
        "You have the following tools available: file::replace, file::write, file::read, shell::execute.\n"
        "In your response:\n"
        "1. State your concise architectural reasoning and plan.\n"
        "2. If providing complete code implementation, specify the file path in the code block header or first line.\n"
        "3. If tests pass cleanly, output TASK_COMPLETE. Otherwise, specify your planned next operational tool/command."
    )

    req_obj = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": "You are an expert software engineer. Do NOT use internal call: or tool-calling syntax. Output your thoughts, reasoning, and tool requests as standard text or JSON markdown code blocks."}]},
        "generationConfig": {
            "thinkingConfig": {
                "thinkingBudget": 16384
            }
        }
    }

    payload = {
        "project": "aicode-consumers",
        "model": "gemini-3.8-flash-tiered",
        "requestId": "debug-test-1",
        "request": req_obj
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "antigravity/1.107.0 darwin/arm64"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("HTTP Status:", resp.status)
            lines = []
            for _ in range(30):
                line = resp.readline().decode("utf-8")
                if not line:
                    break
                lines.append(line.strip())
            print("\n".join(lines[:20]))
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code, e.read().decode("utf-8"))
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    test()
