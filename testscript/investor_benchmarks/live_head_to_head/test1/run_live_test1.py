import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path("/tmp/live_test1_ws")
ETTA_WS = BASE_DIR / "etta_ws"
AGY_WS = BASE_DIR / "agy_ws"
LOGS_DIR = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/testscript/investor_benchmarks/live_head_to_head/test1")

GOAL = (
    "In src/lib.rs, implement `pub fn run_filtered_settlement(batches: &mut [TelemetryRecordBatch1]) -> f64` "
    "that iterates over batches, ignores any record where is_anomaly() is true, and returns the sum of calculate_weighted_index(). "
    "Make sure `cargo test` passes cleanly."
)

def create_repo(ws: Path):
    ws.mkdir(parents=True, exist_ok=True)
    src_dir = ws / "src"
    src_dir.mkdir(exist_ok=True)
    tests_dir = ws / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    lines = [
        "// Enterprise Financial Telemetry Engine v4.8",
        "// High-throughput real-time risk settlement pipeline",
        "use std::collections::HashMap;",
        "",
    ]
    
    # 149 batches = 2,843 lines
    for i in range(1, 150):
        lines.append(f"#[derive(Debug, Clone)]")
        lines.append(f"pub struct TelemetryRecordBatch{i} {{")
        lines.append(f"    pub batch_id: u64,")
        lines.append(f"    pub timestamp_ns: u64,")
        lines.append(f"    pub symbol: String,")
        lines.append(f"    pub volume_profile: Vec<f64>,")
        lines.append(f"    pub bid_ask_spread: f64,")
        lines.append(f"    pub metrics_payload: HashMap<String, f64>,")
        lines.append(f"}}")
        lines.append("")
        lines.append(f"impl TelemetryRecordBatch{i} {{")
        lines.append(f"    pub fn calculate_weighted_index(&self) -> f64 {{")
        lines.append(f"        self.metrics_payload.values().sum::<f64>() * self.bid_ask_spread")
        lines.append(f"    }}")
        lines.append(f"    pub fn is_anomaly(&self) -> bool {{")
        lines.append(f"        self.bid_ask_spread > 0.05 || self.volume_profile.is_empty()")
        lines.append(f"    }}")
        lines.append(f"}}")
        lines.append("")

    lines.append("// Target processor function")
    lines.append("pub fn aggregate_settlement_pipeline(records: &mut [TelemetryRecordBatch1]) -> f64 {")
    lines.append("    let mut total = 0.0;")
    lines.append("    for r in records.iter_mut() { total += r.calculate_weighted_index(); }")
    lines.append("    total")
    lines.append("}")
    lines.append("")

    (src_dir / "lib.rs").write_text("\n".join(lines), encoding="utf-8")
    
    cargo_toml = """[package]
name = "enterprise-telemetry"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
    (ws / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")
    
    # Acceptance test requiring run_filtered_settlement
    acceptance_test = """use enterprise_telemetry::*;
use std::collections::HashMap;

#[test]
fn test_run_filtered_settlement() {
    let mut map1 = HashMap::new();
    map1.insert("price".to_string(), 100.0);
    let mut map2 = HashMap::new();
    map2.insert("price".to_string(), 200.0);

    let mut batches = vec![
        TelemetryRecordBatch1 {
            batch_id: 1,
            timestamp_ns: 1000,
            symbol: "AAPL".to_string(),
            volume_profile: vec![1.0, 2.0],
            bid_ask_spread: 0.01,
            metrics_payload: map1,
        },
        TelemetryRecordBatch1 {
            batch_id: 2,
            timestamp_ns: 2000,
            symbol: "GOOGL".to_string(),
            volume_profile: vec![],
            bid_ask_spread: 0.10, // Anomaly!
            metrics_payload: map2,
        },
    ];

    let result = run_filtered_settlement(&mut batches);
    assert!((result - 1.0).abs() < 1e-5, "Expected 1.0, got {}", result);
}
"""
    (tests_dir / "acceptance_test.rs").write_text(acceptance_test, encoding="utf-8")

def main():
    print("Setting up identical 2,841-line Rust workspaces with acceptance tests...")
    import shutil
    if BASE_DIR.exists():
        shutil.rmtree(BASE_DIR, ignore_errors=True)
    create_repo(ETTA_WS)
    create_repo(AGY_WS)
    
    # Verify starter repo fails cargo test because run_filtered_settlement is missing
    pre_test = subprocess.run(["cargo", "test"], cwd=str(ETTA_WS), capture_output=True, text=True)
    assert pre_test.returncode != 0, "Starter repo must fail cargo test before implementation!"
    print("✅ Verified starter repo fails cargo test (function not yet implemented).")
    
    # 1. LIVE RUN ETTA
    print("\n" + "=" * 65)
    print("1. RUNNING LIVE ETTA HEADLESS ON 2,841-LINE MONOLITH")
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
    etta_proc = subprocess.run(etta_cmd, capture_output=True, text=True, timeout=180)
    etta_wall_time = time.perf_counter() - t0_etta
    
    (LOGS_DIR / "etta_raw.log").write_text(etta_proc.stdout + "\n" + etta_proc.stderr, encoding="utf-8")
    
    # Parse ETTA JSON
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
    print(f"ETTA Complete in {etta_wall_time:.2f}s | Tests Pass: {etta_passes} | Tokens: {etta_data.get('tokens_used', 0)} ({etta_data.get('input_tokens', 0)} in / {etta_data.get('output_tokens', 0)} out)")

    # 2. LIVE RUN AGY
    print("\n" + "=" * 65)
    print("2. RUNNING LIVE AGY ON 2,843-LINE MONOLITH")
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
    agy_proc = subprocess.run(agy_cmd, cwd=str(AGY_WS), capture_output=True, text=True, timeout=300)
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
    print(f"AGY Complete in {agy_wall_time:.2f}s | Tests Pass: {agy_passes} | Tokens: {agy_data.get('usage', {}).get('total_tokens', 0)}")

    RATE_IN = 0.75 / 1e6
    RATE_OUT = 3.75 / 1e6
    
    etta_in = etta_data.get("input_tokens", 0)
    etta_out = etta_data.get("output_tokens", 0)
    etta_tot = etta_data.get("tokens_used", 0)
    etta_cost = round(etta_in * RATE_IN + etta_out * RATE_OUT, 6)

    agy_usage = agy_data.get("usage", {})
    agy_in = agy_usage.get("input_tokens", 0)
    agy_out = agy_usage.get("output_tokens", 0)
    agy_tot = agy_usage.get("total_tokens", 0)
    agy_cost = round(agy_in * RATE_IN + agy_out * RATE_OUT, 6)

    res = {
        "benchmark_id": 1,
        "name": "Live Head-to-Head: Monolithic 2,841-Line Refactor",
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "goal": GOAL,
        "starter_repo": {
            "total_lines": 2841,
            "struct_count": 149,
            "pre_implementation_test_passed": False
        },
        "etta": {
            "provider": etta_data.get("provider", "google"),
            "model": etta_data.get("model", "gemini-3.8-flash-high"),
            "thinking_level": etta_data.get("thinking_level", "high"),
            "status": etta_data.get("status"),
            "exit_code": etta_data.get("exit_code"),
            "wall_time_seconds": round(etta_wall_time, 2),
            "tokens_used": etta_tot,
            "input_tokens": etta_in,
            "output_tokens": etta_out,
            "thinking_tokens": etta_data.get("thinking_tokens", 0),
            "cargo_test_passed": etta_passes,
            "cost_usd": etta_cost,
        },
        "agy": {
            "provider": "google",
            "model": "gemini-3.8-flash-high",
            "thinking_level": "high",
            "status": agy_data.get("status"),
            "exit_code": 0 if agy_passes else 1,
            "wall_time_seconds": round(agy_wall_time, 2),
            "tokens_used": agy_tot,
            "input_tokens": agy_in,
            "output_tokens": agy_out,
            "thinking_tokens": agy_usage.get("thinking_tokens", 0),
            "cache_read_tokens": agy_usage.get("cache_read_tokens", 0),
            "cargo_test_passed": agy_passes,
            "cost_usd": agy_cost,
        },
        "variance": {
            "token_ratio": round(agy_tot / max(1, etta_tot), 2),
            "cost_savings_pct": round((1.0 - etta_cost / max(0.0001, agy_cost)) * 100.0, 2) if agy_cost > 0 else 0.0
        }
    }

    (LOGS_DIR / "live_test1_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n✅ Saved live_test1_results.json successfully!")

if __name__ == "__main__":
    main()
