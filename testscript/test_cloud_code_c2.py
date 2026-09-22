#!/usr/bin/env python3
"""
Diagnostic test script to inspect raw Cloud Code SSE response for Challenge 2.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

def get_token():
    home = Path.home()
    profiles_dir = home / ".gemini" / "profiles"
    active_txt = profiles_dir / "active.txt"
    if not active_txt.exists():
        raise RuntimeError("active.txt not found")
    active_account = active_txt.read_text().strip()
    token_file = profiles_dir / active_account / "jetski-standalone-oauth-token"
    if not token_file.exists():
        raise RuntimeError(f"Token file not found for {active_account}")
    data = json.loads(token_file.read_text())
    token = data.get("token", {}).get("access_token")
    if not token:
        token = data.get("access_token")
    return token, active_account

def test_cloud_code():
    token, account = get_token()
    print(f"Active Account: {account}")
    print(f"Token Prefix: {token[:15]}...")

    goal = (
        "In src/lib.rs, fix the concurrency deadlock and dirty read bugs in MvccEngine "
        "by enforcing monotonic lock hierarchy: Rank 1 active_txs, Rank 2 index across methods "
        "get, commit, garbage_collect."
    )

    prompt = (
        "You are an expert autonomous software engineer solving a coding task.\n"
        f"Objective: {goal}\nTurn: 1\n"
        "Solve this task directly and efficiently.\n"
        "You have the following tools available: file::replace, file::write, file::read, shell::execute.\n"
        "In your response:\n"
        "1. State your concise architectural reasoning and plan.\n"
        "2. If providing complete code implementation, specify the file path in the code block header or first line.\n"
        "3. If tests pass cleanly and all requirements are met, end your response with 'TASK_COMPLETE'. Otherwise, specify your planned next operational tool/command."
    )

    req_obj = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {
            "parts": [{"text": "You are a concise, accurate AI assistant. Adhere strictly to the requested output format."}]
        },
        "generationConfig": {
            "thinkingConfig": {
                "thinkingBudget": 4096
            }
        }
    }

    models_to_test = [
        "gemini-3.8-flash-tiered",
        "gemini-3.8-flash-high",
        "gemini-2.5-flash",
        "gemini-3.1-pro-high",
    ]

    for test_model in models_to_test:
        print(f"\n==========================================")
        print(f"Testing model: {test_model}")
        print(f"==========================================")
        payload = {
            "project": "aicode-consumers",
            "model": test_model,
            "requestId": "test-req-12345",
            "request": req_obj
        }

        url = "https://daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse"
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

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"HTTP Status: {resp.status}")
                chunk_count = 0
                for line in resp:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if line_str.startswith("data:"):
                        chunk_count += 1
                        data_str = line_str[5:].strip()
                        if data_str == "[DONE]":
                            print("Received [DONE]")
                            break
                        if chunk_count <= 2:
                            print(f"  Raw Chunk #{chunk_count}: {data_str[:250]}")
                        try:
                            parsed = json.loads(data_str)
                            cands = parsed.get("response", {}).get("candidates") or parsed.get("candidates", [])
                            for c in cands:
                                parts = c.get("content", {}).get("parts") or c.get("parts", [])
                                for p in parts:
                                    is_th = p.get("thought", False)
                                    txt = p.get("text", "")
                                    preview = txt[:60].replace("\n", " ")
                                    print(f"  Chunk #{chunk_count} [thought={is_th}] len={len(txt)}: {preview}")
                        except Exception as e:
                            print(f"  Chunk #{chunk_count} parse error: {e}")
                                    txt = p.get("text", "")
                                    preview = txt[:60].replace("\n", " ")
                                    print(f"  Chunk #{chunk_count} [thought={is_th}] len={len(txt)}: {preview}")
                        except Exception as e:
                            print(f"  Chunk #{chunk_count} parse error: {e}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"HTTP Error {e.code}: {err_body[:200]}")

if __name__ == "__main__":
    test_cloud_code()
