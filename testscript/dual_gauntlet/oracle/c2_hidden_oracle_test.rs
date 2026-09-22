use mvcc_storage::{MvccEngine, StorageError, TxStatus};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

#[test]
fn test_oracle_concurrency_stress_and_deadlock_elimination() {
    let engine = Arc::new(MvccEngine::new());
    let stop = Arc::new(AtomicBool::new(false));
    let dirty_reads_found = Arc::new(AtomicU64::new(0));

    let mut handles = vec![];

    // 16 Concurrent writers
    for worker_id in 0..16 {
        let eng = engine.clone();
        let stp = stop.clone();
        handles.push(thread::spawn(move || {
            let mut seq = 0;
            while !stp.load(Ordering::Relaxed) && seq < 100 {
                let tx = eng.begin();
                let key = format!("k_{}", seq % 10);
                let val = format!("val_{}_{}", worker_id, seq);
                if eng.write(tx, &key, &val).is_ok() {
                    let _ = eng.commit(tx);
                }
                seq += 1;
            }
        }));
    }

    // 16 Concurrent readers checking snapshot isolation
    for _ in 0..16 {
        let eng = engine.clone();
        let stp = stop.clone();
        let dirty = dirty_reads_found.clone();
        handles.push(thread::spawn(move || {
            let mut iters = 0;
            while !stp.load(Ordering::Relaxed) && iters < 100 {
                let tx = eng.begin();
                let snap = eng.snapshot(tx);
                for k in 0..10 {
                    let key = format!("k_{}", k);
                    if let Some(v) = eng.get(&snap, &key) {
                        if v.is_empty() {
                            dirty.fetch_add(1, Ordering::SeqCst);
                        }
                    }
                }
                iters += 1;
            }
        }));
    }

    // 4 Concurrent GC threads aggressively running to provoke lock inversion
    for _ in 0..4 {
        let eng = engine.clone();
        let stp = stop.clone();
        handles.push(thread::spawn(move || {
            while !stp.load(Ordering::Relaxed) {
                eng.garbage_collect();
                thread::yield_now();
            }
        }));
    }

    let (done_tx, done_rx) = std::sync::mpsc::channel();
    let join_thread = thread::spawn(move || {
        // Wait for workers
        thread::sleep(Duration::from_millis(1500));
        stop.store(true, Ordering::SeqCst);
        for h in handles {
            let _ = h.join();
        }
        let _ = done_tx.send(());
    });

    match done_rx.recv_timeout(Duration::from_secs(6)) {
        Ok(_) => {
            let _ = join_thread.join();
        }
        Err(_) => {
            panic!("ORACLE FAILED: Deadlock detected under concurrent GC/commit load (>6s)!");
        }
    }

    assert_eq!(dirty_reads_found.load(Ordering::SeqCst), 0, "ORACLE FAILED: Dirty reads observed!");
}
