import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path("/tmp/live_test3_ws")
ETTA_WS = BASE_DIR / "etta_ws"
AGY_WS = BASE_DIR / "agy_ws"
LOGS_DIR = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/testscript/investor_benchmarks/live_head_to_head/test3")

GOAL = (
    "In src/lib.rs, implement `commit_tx` and `get` for `MvccEngine`. "
    "In `commit_tx`, verify tx_id is in active_txs, insert mutations into index, and remove tx_id from active_txs. "
    "In `get`, verify tx_id is active and lookup the latest version <= tx_id from index. "
    "CRITICAL: Keep lock acquisition ordering between active_txs and index consistent across all methods to prevent deadlocks under high concurrency. "
    "Verify `cargo test` passes cleanly."
)

def create_starter_workspace(ws: Path):
    ws.mkdir(parents=True, exist_ok=True)
    src_dir = ws / "src"
    src_dir.mkdir(exist_ok=True)
    tests_dir = ws / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    cargo_toml = """[package]
name = "mvcc-engine"
version = "0.1.0"
edition = "2021"

[dependencies]
parking_lot = "0.12"
"""
    (ws / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")
    
    lib_rs = """use parking_lot::Mutex;
use std::collections::{BTreeMap, HashSet};

pub struct MvccEngine {
    pub active_txs: Mutex<HashSet<u64>>,
    pub index: Mutex<BTreeMap<String, Vec<(u64, String)>>>,
    pub next_tx_id: Mutex<u64>,
}

impl MvccEngine {
    pub fn new() -> Self {
        Self {
            active_txs: Mutex::new(HashSet::new()),
            index: Mutex::new(BTreeMap::new()),
            next_tx_id: Mutex::new(1),
        }
    }

    pub fn begin_tx(&self) -> u64 {
        let mut next_id = self.next_tx_id.lock();
        let tx_id = *next_id;
        *next_id += 1;
        let mut active = self.active_txs.lock();
        active.insert(tx_id);
        tx_id
    }

    // Unimplemented: requires agent to implement thread-safe deadlock-free logic
    pub fn commit_tx(&self, _tx_id: u64, _mutations: Vec<(String, String)>) -> bool {
        unimplemented!()
    }

    pub fn get(&self, _tx_id: u64, _key: &str) -> Option<String> {
        unimplemented!()
    }
}
"""
    (src_dir / "lib.rs").write_text(lib_rs, encoding="utf-8")
    
    # 16-thread MVCC concurrency stress test harness
    stress_test = """use mvcc_engine::MvccEngine;
use std::sync::Arc;
use std::thread;
use std::time::Instant;

#[test]
fn test_mvcc_16_thread_concurrency() {
    let engine = Arc::new(MvccEngine::new());
    let mut handles = vec![];
    let start_time = Instant::now();

    // 8 writer threads
    for thread_id in 0..8 {
        let eng = Arc::clone(&engine);
        handles.push(thread::spawn(move || {
            for i in 0..500 {
                let tx = eng.begin_tx();
                let key = format!("key_{}", i % 50);
                let val = format!("val_{}_{}", thread_id, i);
                eng.commit_tx(tx, vec![(key, val)]);
            }
        }));
    }

    // 8 reader threads
    for _ in 0..8 {
        let eng = Arc::clone(&engine);
        handles.push(thread::spawn(move || {
            for i in 0..500 {
                let tx = eng.begin_tx();
                let key = format!("key_{}", i % 50);
                let _ = eng.get(tx, &key);
            }
        }));
    }

    for h in handles {
        h.join().expect("Thread panicked or deadlocked!");
    }

    let elapsed = start_time.elapsed();
    let total_ops = 8000.0;
    let throughput = total_ops / elapsed.as_secs_f64();
    println!("SUCCESS: 8,000 txs in {:?} ({:.0} ops/sec)", elapsed, throughput);
}

#[test]
fn test_basic_mvcc_correctness() {
    let engine = MvccEngine::new();
    let tx1 = engine.begin_tx();
    assert!(engine.commit_tx(tx1, vec![("k1".to_string(), "v1".to_string())]));
    
    let tx2 = engine.begin_tx();
    assert_eq!(engine.get(tx2, "k1"), Some("v1".to_string()));
    assert_eq!(engine.get(tx2, "missing"), None);
}
"""
    (tests_dir / "concurrency_stress.rs").write_text(stress_test, encoding="utf-8")
    # Pre-compile test binary so compilation latency is not charged to agent reasoning
    subprocess.run(["cargo", "test", "--no-run"], cwd=str(ws), capture_output=True)

def main():
    print("Setting up identical MVCC concurrency workspaces...")
    import shutil
    if BASE_DIR.exists():
        shutil.rmtree(BASE_DIR, ignore_errors=True)
    create_starter_workspace(ETTA_WS)
    create_starter_workspace(AGY_WS)
    
    # 1. LIVE RUN ETTA
    print("\n" + "=" * 65)
    print("1. RUNNING LIVE ETTA HEADLESS ON MVCC CONCURRENCY")
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
    etta_proc = subprocess.run(etta_cmd, capture_output=True, text=True, timeout=300)
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

    # Test ETTA with 16-thread stress test (with 30s timeout to catch deadlocks)
    etta_stress_status = "failed"
    etta_throughput = 0.0
    etta_deadlocks = 0
    try:
        etta_stress = subprocess.run(["cargo", "test", "--test", "concurrency_stress", "--", "--nocapture"], cwd=str(ETTA_WS), capture_output=True, text=True, timeout=30)
        if etta_stress.returncode == 0:
            etta_stress_status = "success"
            for line in etta_stress.stdout.splitlines():
                if "ops/sec" in line:
                    parts = line.split("(")
                    if len(parts) > 1:
                        etta_throughput = float(parts[1].split(" ops/sec")[0])
        else:
            print("ETTA stress test failed:", etta_stress.stderr)
    except subprocess.TimeoutExpired:
        print("🔴 ETTA 16-thread stress test DEADLOCKED (timed out after 30s)!")
        etta_deadlocks = 1
        etta_stress_status = "deadlock_timeout"

    print(f"ETTA Complete in {etta_wall_time:.2f}s | Stress: {etta_stress_status} ({etta_throughput:.0f} ops/s) | Tokens: {etta_data.get('tokens_used', 0)}")

    # 2. LIVE RUN AGY
    print("\n" + "=" * 65)
    print("2. RUNNING LIVE AGY ON MVCC CONCURRENCY")
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
    agy_proc = subprocess.run(agy_cmd, cwd=str(AGY_WS), capture_output=True, text=True, timeout=450)
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

    # Test AGY with 16-thread stress test (with 30s timeout to catch deadlocks)
    agy_stress_status = "failed"
    agy_throughput = 0.0
    agy_deadlocks = 0
    try:
        agy_stress = subprocess.run(["cargo", "test", "--test", "concurrency_stress", "--", "--nocapture"], cwd=str(AGY_WS), capture_output=True, text=True, timeout=30)
        if agy_stress.returncode == 0:
            agy_stress_status = "success"
            for line in agy_stress.stdout.splitlines():
                if "ops/sec" in line:
                    parts = line.split("(")
                    if len(parts) > 1:
                        agy_throughput = float(parts[1].split(" ops/sec")[0])
        else:
            print("AGY stress test failed:", agy_stress.stderr)
    except subprocess.TimeoutExpired:
        print("🔴 AGY 16-thread stress test DEADLOCKED (timed out after 10s)!")
        agy_deadlocks = 1
        agy_stress_status = "deadlock_timeout"

    print(f"AGY Complete in {agy_wall_time:.2f}s | Stress: {agy_stress_status} ({agy_throughput:.0f} ops/s) | Tokens: {agy_data.get('usage', {}).get('total_tokens', 0)}")

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
        "benchmark_id": 3,
        "name": "Live Head-to-Head: Concurrent MVCC Code Generation & 16-Thread Stress",
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "workload": "16 concurrent threads (8 writers, 8 readers) executing 8,000 MVCC transactions",
        "goal": GOAL,
        "etta": {
            "provider": etta_data.get("provider", "google"),
            "model": etta_data.get("model", "gemini-3.8-flash-high"),
            "thinking_level": etta_data.get("thinking_level", "high"),
            "status": etta_stress_status,
            "exit_code": etta_data.get("exit_code", 0),
            "deadlocks_observed": etta_deadlocks,
            "throughput_ops_per_sec": etta_throughput,
            "wall_time_seconds": round(etta_wall_time, 2),
            "tokens_used": etta_tot,
            "input_tokens": etta_in,
            "output_tokens": etta_out,
            "thinking_tokens": etta_data.get("thinking_tokens", 0),
            "cost_usd": etta_cost,
        },
        "agy": {
            "provider": "google",
            "model": "gemini-3.8-flash-high",
            "thinking_level": "high",
            "status": agy_stress_status,
            "exit_code": 0 if agy_stress_status == "success" else 1,
            "deadlocks_observed": agy_deadlocks,
            "throughput_ops_per_sec": agy_throughput,
            "wall_time_seconds": round(agy_wall_time, 2),
            "tokens_used": agy_tot,
            "input_tokens": agy_in,
            "output_tokens": agy_out,
            "thinking_tokens": agy_usage.get("thinking_tokens", 0),
            "cost_usd": agy_cost,
        }
    }

    (LOGS_DIR / "live_test3_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n✅ Saved live_test3_results.json successfully!")

if __name__ == "__main__":
    main()
