import sys
from pathlib import Path

WORKSPACE = Path("/tmp/etta_bench_test3_ws")
WORKSPACE.mkdir(parents=True, exist_ok=True)
src_dir = WORKSPACE / "src"
src_dir.mkdir(exist_ok=True)
tests_dir = WORKSPACE / "tests"
tests_dir.mkdir(exist_ok=True)

# Cargo.toml
cargo_toml = """[package]
name = "mvcc-engine"
version = "0.1.0"
edition = "2021"

[dependencies]
parking_lot = "0.12"
"""
(WORKSPACE / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")

# MVCC engine skeleton strictly adhering to INV-ETTA-31
lib_rs = """use parking_lot::Mutex;
use std::collections::{BTreeMap, HashSet};
use std::sync::Arc;

// INV-ETTA-31: Global Monotonic Lock Hierarchy
// Rank 1: active_txs
// Rank 2: index
pub struct MvccEngine {
    // Rank 1
    active_txs: Mutex<HashSet<u64>>,
    // Rank 2
    index: Mutex<BTreeMap<String, Vec<(u64, String)>>>,
    next_tx_id: Mutex<u64>,
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

    // INV-ETTA-31 Canonical Ordering: Lock active_txs (Rank 1) BEFORE index (Rank 2)
    pub fn commit_tx(&self, tx_id: u64, mutations: Vec<(String, String)>) -> bool {
        let mut active = self.active_txs.lock(); // Rank 1
        if !active.contains(&tx_id) {
            return false;
        }

        let mut idx = self.index.lock(); // Rank 2
        for (key, val) in mutations {
            idx.entry(key).or_default().push((tx_id, val));
        }

        active.remove(&tx_id);
        true
    }

    // INV-ETTA-31 Canonical Ordering: Must NOT acquire index (Rank 2) then active_txs (Rank 1)!
    // Must acquire active_txs (Rank 1) first, or acquire separately without overlap.
    pub fn get(&self, tx_id: u64, key: &str) -> Option<String> {
        // Safe reader: snapshot active txs first (Rank 1)
        let is_active = {
            let active = self.active_txs.lock();
            active.contains(&tx_id)
        };
        if !is_active {
            return None;
        }

        // Then acquire index (Rank 2) cleanly
        let idx = self.index.lock();
        idx.get(key).and_then(|versions| {
            versions.iter().rev()
                .find(|(ver, _)| *ver <= tx_id)
                .map(|(_, val)| val.clone())
        })
    }
}
"""
(src_dir / "lib.rs").write_text(lib_rs, encoding="utf-8")

# Stress test: 16 concurrent threads doing 10,000 rapid interleaved operations
stress_test_rs = """use mvcc_engine::MvccEngine;
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

#[test]
fn test_concurrent_mvcc_stress_no_deadlock() {
    let engine = Arc::new(MvccEngine::new());
    let mut handles = Vec::new();

    let start = Instant::now();
    // Spawn 8 writer threads
    for t in 0..8 {
        let eng = Arc::clone(&engine);
        handles.push(thread::spawn(move || {
            for i in 0..500 {
                let tx = eng.begin_tx();
                let key = format!("key_{}", (t * 500 + i) % 50);
                let val = format!("val_{}_{}", t, i);
                eng.commit_tx(tx, vec![(key, val)]);
            }
        }));
    }

    // Spawn 8 reader threads
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
        h.join().expect("Thread panicked");
    }

    let elapsed = start.elapsed();
    println!("Completed 8,000 concurrent MVCC operations in {:?}", elapsed);
    assert!(elapsed < Duration::from_secs(5), "Execution took too long; potential lock contention");
}
"""
(tests_dir / "stress_test.rs").write_text(stress_test_rs, encoding="utf-8")
print(f"Created MVCC concurrency workspace at {WORKSPACE}")
