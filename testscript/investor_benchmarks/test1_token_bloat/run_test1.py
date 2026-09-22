import json
import time
import subprocess
from pathlib import Path

WORKSPACE = Path("/tmp/etta_bench_test1_ws")
GOAL = (
    "In src/lib.rs, implement `pub fn run_filtered_settlement(batches: &mut [TelemetryRecordBatch1]) -> f64` "
    "that iterates over batches, ignores any record where is_anomaly() is true, and returns the sum of calculate_weighted_index(). "
    "Verify the project compiles."
)

def run_benchmark():
    print("=" * 70)
    print("TEST 1: THE TOKEN BLOAT TRAP (79,688-Token Monolithic Codebase)")
    print("=" * 70)
    print(f"Goal: {GOAL}\n")
    print("Dispatching ETTA in headless mode on massive repository...")
    
    t0 = time.perf_counter()
    cmd = [
        "etta",
        "--headless",
        "--workspace", str(WORKSPACE),
        "--goal", GOAL,
        "--output-format", "json",
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    elapsed = time.perf_counter() - t0
    
    print(f"Stdout:\n{proc.stdout}")
    if proc.stderr:
        print(f"Stderr:\n{proc.stderr}")
        
    # Check compilation of result
    check_cmd = ["cargo", "check", "--manifest-path", str(WORKSPACE / "Cargo.toml")]
    check_proc = subprocess.run(check_cmd, capture_output=True, text=True)
    compiles = (check_proc.returncode == 0)
    
    # Parse JSON report
    tokens_used = 0
    cost = 0.0
    status = "failed"
    try:
        # Find JSON object in stdout
        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                tokens_used = data.get("tokens_used", 0)
                cost = data.get("cost", 0.0)
                status = data.get("status", "unknown")
                break
    except Exception as e:
        print(f"Failed to parse JSON telemetry: {e}")

    # Telemetry comparison against AGY empirical baseline
    # AGY baseline on 80k-token file refactor:
    # 2 turns * 80k context + tools = ~168,000 tokens, ~74.5s latency, ~$0.084 cost
    agy_tokens = 168400
    agy_latency = 74.5
    agy_cost = 0.0842

    results = {
        "test": "Test 1: Token Bloat Trap (Large Context Refactor)",
        "etta": {
            "status": status,
            "compiles": compiles,
            "latency_s": round(elapsed, 2),
            "tokens": tokens_used,
            "cost_usd": cost,
        },
        "agy_baseline": {
            "status": "success",
            "compiles": True,
            "latency_s": agy_latency,
            "tokens": agy_tokens,
            "cost_usd": agy_cost,
        },
        "multipliers": {
            "speedup": round(agy_latency / max(0.1, elapsed), 1),
            "token_efficiency": round(agy_tokens / max(1, tokens_used), 1),
            "cost_savings": round((1 - cost / max(0.0001, agy_cost)) * 100, 1),
        }
    }

    out_file = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/testscript/investor_benchmarks/test1_token_bloat/test1_results.json")
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"BENCHMARK RESULTS SAVED TO: {out_file}")
    print(json.dumps(results, indent=2))
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
