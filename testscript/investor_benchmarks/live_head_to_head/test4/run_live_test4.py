import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path("/tmp/live_test4_ws")
ETTA_WS = BASE_DIR / "etta_ws"
AGY_WS = BASE_DIR / "agy_ws"
LOGS_DIR = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/testscript/investor_benchmarks/live_head_to_head/test4")
VENV_PYTHON = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/.venv/bin/python")

import shutil

PROMPT = (
    "Create `auth_service.py` in the current workspace directory using file creation tools. "
    "Implement production Python functions:\n"
    "1. `issue_tokens(user_id: str, secret: str) -> dict`: returns `{'access_token': str, 'refresh_token': str}` using `jwt.encode` (HS256). The token payload must include `'user_id': user_id` and `'sub': user_id`.\n"
    "2. `verify_token(token: str, secret: str) -> dict`: returns decoded payload dictionary using `jwt.decode` (HS256, algorithms=['HS256']).\n"
    "3. `hash_password(password: str) -> str`: hashes password using `bcrypt.hashpw` and `bcrypt.gensalt`, returning string.\n"
    "4. `verify_password(password: str, hashed: str) -> bool`: verifies password using `bcrypt.checkpw`, returning bool.\n"
    "You MUST write the file `auth_service.py` on disk in the current workspace so the test suite can import it. "
    "Run `pytest` to confirm tests pass cleanly."
)

TEST_CONTENT = """import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from auth_service import issue_tokens, verify_token, hash_password, verify_password

def test_token_lifecycle():
    secret = "production_super_secret_key_12345"
    tokens = issue_tokens("user_test_99", secret)
    assert isinstance(tokens, dict)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    
    payload = verify_token(tokens["access_token"], secret)
    assert (payload.get("user_id") or payload.get("sub")) == "user_test_99"

def test_password_hashing():
    pw = "SuperSecurePassword123!"
    hashed = hash_password(pw)
    assert isinstance(hashed, str)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("incorrect_pw", hashed) is False
"""

def setup_workspace(ws: Path):
    ws.mkdir(parents=True, exist_ok=True)
    tests_dir = ws / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_auth.py").write_text(TEST_CONTENT, encoding="utf-8")
    (ws / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")

def main():
    print("Setting up clean workspaces for Test 4...")
    if BASE_DIR.exists():
        shutil.rmtree(BASE_DIR, ignore_errors=True)
    setup_workspace(ETTA_WS)
    setup_workspace(AGY_WS)
    
    RATE_IN = 0.75 / 1e6
    RATE_OUT = 3.75 / 1e6
    INR_RATE = 95.80
    
    env_clean = os.environ.copy()
    env_clean["PATH"] = f"{VENV_PYTHON.parent}:{Path.home()}/.cargo/bin:{env_clean.get('PATH', '')}"
    env_clean["VIRTUAL_ENV"] = str(VENV_PYTHON.parent.parent)

    # 1. LIVE RUN ETTA
    print("\n" + "=" * 65)
    print("1. RUNNING LIVE ETTA HEADLESS ON MULTI-TENANT AUTH SERVICE")
    print("=" * 65)
    t0_etta = time.perf_counter()
    etta_bin = str(Path.home() / ".cargo" / "bin" / "etta")
    cmd_etta = [
        etta_bin,
        "--headless",
        "--workspace", str(ETTA_WS),
        "--goal", PROMPT,
        "--output-format", "json",
    ]
    proc_etta = subprocess.run(cmd_etta, capture_output=True, text=True, timeout=180, env=env_clean)
    etta_wall = time.perf_counter() - t0_etta
    (LOGS_DIR / "etta_raw.log").write_text(proc_etta.stdout + "\n" + proc_etta.stderr, encoding="utf-8")
    
    etta_data = {}
    try:
        idx = proc_etta.stdout.rfind('{\n  "exit_code"')
        if idx != -1:
            etta_data = json.loads(proc_etta.stdout[idx:])
        else:
            idx = proc_etta.stdout.rfind('{')
            if idx != -1:
                etta_data = json.loads(proc_etta.stdout[idx:])
    except Exception as e:
        print("ETTA JSON parse error:", e)

    etta_file = ETTA_WS / "auth_service.py"
    etta_has_file = etta_file.exists() and etta_file.stat().st_size > 50
    
    # Run independent pytest verification
    etta_test_proc = subprocess.run([str(VENV_PYTHON), "-m", "pytest", "tests/test_auth.py"], cwd=str(ETTA_WS), capture_output=True, text=True, env=env_clean)
    etta_pytest_passed = (etta_test_proc.returncode == 0)
    
    etta_in = etta_data.get("input_tokens", 0)
    etta_out = etta_data.get("output_tokens", 0)
    etta_tokens = etta_data.get("tokens_used", 0)
    etta_cost = round(etta_in * RATE_IN + etta_out * RATE_OUT, 6)
    
    print(f"ETTA Complete in {etta_wall:.2f}s | File Created: {etta_has_file} | Pytest Pass: {etta_pytest_passed} | Tokens: {etta_tokens} | Cost: ${etta_cost:.6f} (₹{etta_cost*INR_RATE:.2f})")

    # 2. LIVE RUN AGY
    print("\n" + "=" * 65)
    print("2. RUNNING LIVE AGY PRINT-MODE ON MULTI-TENANT AUTH SERVICE")
    print("=" * 65)
    t0_agy = time.perf_counter()
    cmd_agy = [
        "agy",
        "--add-dir", str(AGY_WS),
        "-p", PROMPT,
        "--model", "gemini-3.8-flash-high",
        "--effort", "high",
        "--dangerously-skip-permissions",
        "--output-format", "json",
    ]
    proc_agy = subprocess.run(cmd_agy, cwd=str(AGY_WS), capture_output=True, text=True, timeout=300, env=env_clean)
    agy_wall = time.perf_counter() - t0_agy
    (LOGS_DIR / "agy_raw.log").write_text(proc_agy.stdout + "\n" + proc_agy.stderr, encoding="utf-8")
    
    agy_data = {}
    try:
        idx = proc_agy.stdout.rfind('{"conversation_id"')
        if idx != -1:
            agy_data = json.loads(proc_agy.stdout[idx:])
        else:
            idx = proc_agy.stdout.rfind('{')
            if idx != -1:
                agy_data = json.loads(proc_agy.stdout[idx:])
    except Exception as e:
        print("AGY JSON parse error:", e)

    agy_file = AGY_WS / "auth_service.py"
    agy_has_file = agy_file.exists() and agy_file.stat().st_size > 50
    
    # Run independent pytest verification
    agy_test_proc = subprocess.run([str(VENV_PYTHON), "-m", "pytest", "tests/test_auth.py"], cwd=str(AGY_WS), capture_output=True, text=True)
    agy_pytest_passed = (agy_test_proc.returncode == 0)

    usage = agy_data.get("usage", {})
    agy_in = usage.get("input_tokens", 0)
    agy_out = usage.get("output_tokens", 0)
    agy_tokens = usage.get("total_tokens", agy_in + agy_out)
    agy_cost = round(agy_in * RATE_IN + agy_out * RATE_OUT, 6)
    
    print(f"AGY Complete in {agy_wall:.2f}s | File Created: {agy_has_file} | Pytest Pass: {agy_pytest_passed} | Tokens: {agy_tokens} | Cost: ${agy_cost:.6f} (₹{agy_cost*INR_RATE:.2f})")

    report = {
        "benchmark_id": 4,
        "name": "Live Head-to-Head: Greenfield Multi-Tenant Auth Service Synthesis",
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "prompt": PROMPT,
        "exchange_rate": f"1 USD = {INR_RATE:.2f} INR",
        "etta": {
            "provider": etta_data.get("provider", "google"),
            "model": etta_data.get("model", "gemini-3.8-flash-high"),
            "thinking_level": etta_data.get("thinking_level", "high"),
            "wall_clock_seconds": round(etta_wall, 2),
            "file_created": etta_has_file,
            "pytest_passed": etta_pytest_passed,
            "status": etta_data.get("status", "success" if (etta_has_file and etta_pytest_passed) else "failed"),
            "exit_code": etta_data.get("exit_code", 0 if (etta_has_file and etta_pytest_passed) else 1),
            "tokens_used": etta_tokens,
            "input_tokens": etta_in,
            "output_tokens": etta_out,
            "thinking_tokens": etta_data.get("thinking_tokens", 0),
            "cost_usd": etta_cost,
            "cost_inr": round(etta_cost * INR_RATE, 4),
        },
        "agy": {
            "provider": "google",
            "model": "gemini-3.8-flash-high",
            "thinking_level": "high",
            "wall_clock_seconds": round(agy_wall, 2),
            "file_created": agy_has_file,
            "pytest_passed": agy_pytest_passed,
            "status": "success" if (agy_has_file and agy_pytest_passed) else "failed",
            "exit_code": 0 if (agy_has_file and agy_pytest_passed) else 1,
            "tokens_used": agy_tokens,
            "input_tokens": agy_in,
            "output_tokens": agy_out,
            "thinking_tokens": usage.get("thinking_tokens", 0),
            "cost_usd": agy_cost,
            "cost_inr": round(agy_cost * INR_RATE, 4),
        },
        "variance": {
            "token_ratio": round(agy_tokens / max(1, etta_tokens), 2),
            "cost_savings_pct": round((1 - etta_cost / max(0.000001, agy_cost)) * 100, 2)
        }
    }
    
    res_path = LOGS_DIR / "live_test4_results.json"
    res_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n✅ Saved live_test4_results.json successfully!")

if __name__ == "__main__":
    main()
