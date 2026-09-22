import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path("/tmp/live_test2_ws")
ETTA_WS = BASE_DIR / "etta_ws"
AGY_WS = BASE_DIR / "agy_ws"
LOGS_DIR = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/testscript/investor_benchmarks/live_head_to_head/test2")

GOAL = (
    "Run `cargo test`. If it fails, locate the boundary bug in src/lib.rs and fix `try_consume` so that "
    "`cargo test` passes 100%. Verify cargo test passes."
)

def create_workspace(ws: Path):
    ws.mkdir(parents=True, exist_ok=True)
    src_dir = ws / "src"
    src_dir.mkdir(exist_ok=True)
    tests_dir = ws / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    cargo_toml = """[package]
name = "strict-vault"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
    (ws / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")
    
    lib_rs = """// Thread-safe Token Bucket Rate Limiter
pub struct TokenBucket {
    pub capacity: u64,
    pub current_tokens: u64,
}

impl TokenBucket {
    pub fn new(capacity: u64) -> Self {
        Self { capacity, current_tokens: capacity }
    }

    pub fn try_consume(&mut self, tokens: u64) -> bool {
        // Buggy: strictly greater than instead of greater than or equal to
        if self.current_tokens > tokens {
            self.current_tokens -= tokens;
            true
        } else {
            false
        }
    }
}
"""
    (src_dir / "lib.rs").write_text(lib_rs, encoding="utf-8")
    
    test_rs = """use strict_vault::TokenBucket;

#[test]
fn test_exact_capacity_consumption() {
    let mut bucket = TokenBucket::new(10);
    assert!(bucket.try_consume(10), "Consuming exact capacity (10 tokens from 10) must succeed");
    assert_eq!(bucket.current_tokens, 0);
}
"""
    (tests_dir / "boundary_test.rs").write_text(test_rs, encoding="utf-8")

def main():
    print("Setting up identical TokenBucket workspaces...")
    import shutil
    if BASE_DIR.exists():
        shutil.rmtree(BASE_DIR, ignore_errors=True)
    create_workspace(ETTA_WS)
    create_workspace(AGY_WS)
    
    # 1. LIVE RUN ETTA
    print("\n" + "=" * 65)
    print("1. RUNNING LIVE ETTA HEADLESS ON BOUNDARY BUG")
    print("=" * 65)
    t0_etta = time.perf_counter()
    etta_bin = str(Path.home() / ".cargo" / "bin" / "etta")
    etta_cmd = [
        etta_bin,
        "--headless",
        "--workspace", str(ETTA_WS),
        "--goal", GOAL,
        "--output-format", "json",
    ]
    etta_proc = subprocess.run(etta_cmd, capture_output=True, text=True, timeout=120)
    etta_wall_time = time.perf_counter() - t0_etta
    
    (LOGS_DIR / "etta_raw.log").write_text(etta_proc.stdout + "\n" + etta_proc.stderr, encoding="utf-8")
    
    etta_data = {}
    try:
        idx = etta_proc.stdout.rfind('{\n  "exit_code"')
        if idx != -1:
            etta_data = json.loads(etta_proc.stdout[idx:])
        else:
            idx = etta_proc.stdout.rfind('{')
            if idx != -1:
                etta_data = json.loads(etta_proc.stdout[idx:])
    except Exception as e:
        print("ETTA JSON parse error:", e)
                
    etta_test = subprocess.run(["cargo", "test"], cwd=str(ETTA_WS), capture_output=True, text=True)
    etta_passes = (etta_test.returncode == 0)
    print(f"ETTA Complete in {etta_wall_time:.2f}s | Tests Pass: {etta_passes} | Tokens: {etta_data.get('tokens_used', 0)}")

    # 2. LIVE RUN AGY
    print("\n" + "=" * 65)
    print("2. RUNNING LIVE AGY ON BOUNDARY BUG")
    print("=" * 65)
    t0_agy = time.perf_counter()
    agy_cmd = [
        "agy",
        "--add-dir", str(AGY_WS),
        "-p", GOAL,
        "--model", "gemini-3.8-flash-high",
        "--effort", "high",
        "--dangerously-skip-permissions",
        "--output-format", "json",
    ]
    agy_proc = subprocess.run(agy_cmd, cwd=str(AGY_WS), capture_output=True, text=True, timeout=120)
    agy_wall_time = time.perf_counter() - t0_agy
    
    (LOGS_DIR / "agy_raw.log").write_text(agy_proc.stdout + "\n" + agy_proc.stderr, encoding="utf-8")
    
    agy_data = {}
    try:
        idx = agy_proc.stdout.rfind('{"conversation_id"')
        if idx != -1:
            agy_data = json.loads(agy_proc.stdout[idx:])
        else:
            idx = agy_proc.stdout.rfind('{')
            if idx != -1:
                agy_data = json.loads(agy_proc.stdout[idx:])
    except Exception as e:
        print("AGY JSON parse error:", e)
                
    agy_test = subprocess.run(["cargo", "test"], cwd=str(AGY_WS), capture_output=True, text=True)
    agy_passes = (agy_test.returncode == 0)
    agy_usage = agy_data.get("usage", {})
    agy_tokens = agy_usage.get("total_tokens", 0)
    agy_in = agy_usage.get("input_tokens", 0)
    agy_out = agy_usage.get("output_tokens", 0)
    agy_cost = round(agy_in * 0.00000075 + agy_out * 0.00000375, 6)
    print(f"AGY Complete in {agy_wall_time:.2f}s | Tests Pass: {agy_passes} | Tokens: {agy_tokens} | Cost: ${agy_cost:.6f}")

    etta_in = etta_data.get("input_tokens", 0)
    etta_out = etta_data.get("output_tokens", 0)
    etta_cost = round(etta_in * 0.00000075 + etta_out * 0.00000375, 6)

    report = {
        "benchmark_id": 2,
        "name": "Live Head-to-Head: The Hallucinated Success Trap (Boundary Defect)",
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "etta": {
            "provider": etta_data.get("provider", "google"),
            "model": etta_data.get("model", "gemini-3.8-flash-high"),
            "thinking_level": etta_data.get("thinking_level", "high"),
            "wall_clock_seconds": round(etta_wall_time, 2),
            "tests_passed": etta_passes,
            "tokens_used": etta_data.get("tokens_used", 0),
            "input_tokens": etta_in,
            "output_tokens": etta_out,
            "thinking_tokens": etta_data.get("thinking_tokens", 0),
            "cost_usd": etta_cost,
            "status": etta_data.get("status", "unknown"),
            "exit_code": etta_data.get("exit_code", 0 if etta_passes else 1),
            "raw_output_file": str(LOGS_DIR / "etta_raw.log"),
        },
        "agy": {
            "provider": "google",
            "model": "gemini-3.8-flash-high",
            "thinking_level": "high",
            "wall_clock_seconds": round(agy_wall_time, 2),
            "duration_seconds": agy_data.get("duration_seconds", round(agy_wall_time, 2)),
            "tests_passed": agy_passes,
            "num_turns": agy_data.get("num_turns", 1),
            "input_tokens": agy_usage.get("input_tokens", 0),
            "output_tokens": agy_usage.get("output_tokens", 0),
            "thinking_tokens": agy_usage.get("thinking_tokens", 0),
            "total_tokens": agy_tokens,
            "cost_usd": agy_cost,
            "status": agy_data.get("status", "unknown"),
            "exit_code": 0 if agy_passes else 1,
            "raw_output_file": str(LOGS_DIR / "agy_raw.log"),
        },
        "variance": {
            "token_ratio": round(agy_tokens / max(1, etta_data.get("tokens_used", 1)), 2),
            "cost_savings_pct": round((1 - etta_cost / max(0.000001, agy_cost)) * 100, 2),
        }
    }

    res_path = LOGS_DIR / "live_test2_results.json"
    res_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n" + "=" * 65)
    print(f"LIVE RESULTS SAVED TO: {res_path}")
    print(json.dumps(report, indent=2))
    print("=" * 65)

if __name__ == "__main__":
    main()
