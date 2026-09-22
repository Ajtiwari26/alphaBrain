use mvcc_storage::MvccEngine;
use std::sync::Arc;
use std::thread;

#[test]
fn test_concurrent_commit_and_snapshot() {
    let engine = Arc::new(MvccEngine::new());
    let mut handles = vec![];

    // Spawn 8 concurrent threads writing and snapshotting
    for i in 0..8 {
        let engine_clone = engine.clone();
        handles.push(thread::spawn(move || {
            for j in 0..20 {
                let tx = engine_clone.begin();
                let key = format!("user_{}", i);
                let val = format!("val_{}_{}", i, j);
                
                engine_clone.write(tx, &key, &val).unwrap();
                engine_clone.commit(tx).unwrap();

                let reader_tx = engine_clone.begin();
                let snap = engine_clone.snapshot(reader_tx);
                let _ = engine_clone.get(&snap, &key);
            }
        }));
    }

    // Background garbage collection thread inducing AB-BA lock inversion
    let gc_engine = engine.clone();
    let gc_handle = thread::spawn(move || {
        for _ in 0..30 {
            gc_engine.garbage_collect();
            thread::yield_now();
        }
    });

    let (done_tx, done_rx) = std::sync::mpsc::channel();

    let runner = thread::spawn(move || {
        for h in handles {
            h.join().expect("Worker thread panicked or crashed due to race condition!");
        }
        gc_handle.join().expect("GC thread deadlocked or crashed!");
        let _ = done_tx.send(());
    });

    // Bounded 5-second watchdog to catch deadlock immediately
    match done_rx.recv_timeout(std::time::Duration::from_secs(5)) {
        Ok(_) => {
            let _ = runner.join();
        }
        Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
            panic!("DEADLOCK OR RACE CONDITION DETECTED: Concurrency lock inversion halted execution for >5s!");
        }
        Err(e) => panic!("Test failed: {:?}", e),
    }
}
