use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use parking_lot::RwLock;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum StorageError {
    #[error("transaction {0} not found or inactive")]
    TransactionNotFound(u64),
    #[error("serialization conflict on key {0}")]
    WriteConflict(String),
    #[error("transaction aborted")]
    Aborted,
    #[error("lock timeout / deadlock detected")]
    Deadlock,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TxStatus {
    Active,
    Committed,
    Aborted,
}

#[derive(Clone, Debug)]
pub struct VersionRecord {
    pub tx_id: u64,
    pub commit_id: Option<u64>,
    pub value: String,
    pub is_deleted: bool,
}

#[derive(Clone, Debug)]
pub struct Snapshot {
    pub read_tx_id: u64,
    pub watermark: u64,
    pub active_set: HashSet<u64>,
}

pub struct MvccEngine {
    tx_counter: AtomicU64,
    commit_counter: AtomicU64,
    active_txs: Arc<RwLock<HashMap<u64, TxStatus>>>,
    index: Arc<RwLock<HashMap<String, Vec<VersionRecord>>>>,
}

impl MvccEngine {
    pub fn new() -> Self {
        Self {
            tx_counter: AtomicU64::new(1),
            commit_counter: AtomicU64::new(1),
            active_txs: Arc::new(RwLock::new(HashMap::new())),
            index: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn begin(&self) -> u64 {
        let tx_id = self.tx_counter.fetch_add(1, Ordering::SeqCst);
        let mut txs = self.active_txs.write();
        txs.insert(tx_id, TxStatus::Active);
        tx_id
    }

    pub fn snapshot(&self, read_tx_id: u64) -> Snapshot {
        let txs = self.active_txs.read();
        let watermark = self.commit_counter.load(Ordering::SeqCst);
        let active_set: HashSet<u64> = txs
            .iter()
            .filter(|(&id, &status)| id != read_tx_id && status == TxStatus::Active)
            .map(|(&id, _)| id)
            .collect();

        Snapshot {
            read_tx_id,
            watermark,
            active_set,
        }
    }

    pub fn write(&self, tx_id: u64, key: &str, value: &str) -> Result<(), StorageError> {
        let txs = self.active_txs.read();
        if txs.get(&tx_id) != Some(&TxStatus::Active) {
            return Err(StorageError::TransactionNotFound(tx_id));
        }

        let mut index = self.index.write();
        let versions = index.entry(key.to_string()).or_insert_with(Vec::new);

        // Check for write conflicts
        if let Some(latest) = versions.last() {
            if latest.commit_id.is_none() && latest.tx_id != tx_id {
                return Err(StorageError::WriteConflict(key.to_string()));
            }
        }

        versions.push(VersionRecord {
            tx_id,
            commit_id: None,
            value: value.to_string(),
            is_deleted: false,
        });

        Ok(())
    }

    // BUG (CONCURRENCY TOCTOU & LOCK INVERSION):
    // 1. In this buggy implementation, active_txs is locked and updated BEFORE
    //    the index locks are acquired and committed.
    // 2. A concurrent snapshot can see the transaction marked as Committed,
    //    but the version record in `index` still has commit_id == None!
    // 3. Furthermore, the lock acquisition order in commit() is:
    //    active_txs.write() -> index.write()
    //    While garbage_collect() acquires:
    //    index.write() -> active_txs.write()
    //    This creates an AB-BA deadlock hazard under concurrent load!
    pub fn commit(&self, tx_id: u64) -> Result<u64, StorageError> {
        // Buggy Order: Locks active_txs FIRST
        let mut txs = self.active_txs.write();
        if txs.get(&tx_id) != Some(&TxStatus::Active) {
            return Err(StorageError::TransactionNotFound(tx_id));
        }

        let commit_id = self.commit_counter.fetch_add(1, Ordering::SeqCst);
        
        // Mark committed in active_txs before updating index versions!
        txs.insert(tx_id, TxStatus::Committed);

        // Sleep/yield point makes race condition reproducible
        std::thread::yield_now();

        // Lock index SECOND (Lock inversion hazard)
        let mut index = self.index.write();
        for versions in index.values_mut() {
            for v in versions.iter_mut() {
                if v.tx_id == tx_id && v.commit_id.is_none() {
                    v.commit_id = Some(commit_id);
                }
            }
        }

        Ok(commit_id)
    }

    pub fn get(&self, snapshot: &Snapshot, key: &str) -> Option<String> {
        let index = self.index.read();
        let versions = index.get(key)?;

        for v in versions.iter().rev() {
            // Invisible if created by another transaction that was active when snapshot began
            if snapshot.active_set.contains(&v.tx_id) {
                continue;
            }

            // Visible if created by our own transaction
            if v.tx_id == snapshot.read_tx_id {
                return if v.is_deleted { None } else { Some(v.value.clone()) };
            }

            // Visible if committed before snapshot watermark
            if let Some(cid) = v.commit_id {
                if cid <= snapshot.watermark {
                    return if v.is_deleted { None } else { Some(v.value.clone()) };
                }
            } else {
                // Check if active_txs thinks it's committed (DIRTY READ HAZARD)
                let txs = self.active_txs.read();
                if txs.get(&v.tx_id) == Some(&TxStatus::Committed) {
                    // TOCTOU BUG: Reading uncommitted or partially committed version!
                    panic!("FATAL CONCURRENCY BUG: Read view observed dirty unversioned record for tx {}", v.tx_id);
                }
            }
        }

        None
    }

    pub fn garbage_collect(&self) {
        // Lock inversion hazard: Locks index FIRST, then active_txs
        let mut index = self.index.write();
        let mut txs = self.active_txs.write();

        txs.retain(|_, &mut status| status == TxStatus::Active);
        
        let oldest_active = txs.keys().copied().min().unwrap_or(u64::MAX);

        for versions in index.values_mut() {
            if versions.len() > 1 {
                versions.retain(|v| {
                    v.commit_id.is_none() || v.commit_id.unwrap() >= oldest_active
                });
            }
        }
    }
}
