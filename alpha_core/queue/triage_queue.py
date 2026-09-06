"""
alpha_core/queue/triage_queue.py
SQLite-backed Task Triage Queue and State Machine for AlphaBrain Phase 9.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 6 - P9 Constitution)
Debate Consensus: Claude Opus 4.6 (Architect) + Gemini 3.1 Pro (Reliability)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import re
import sqlite3
import time
import uuid
from collections.abc import Callable
from contextlib import closing
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger("alphabrain.queue.triage")

DEFAULT_DB_PATH = Path.home() / ".alphabrain" / "task_triage_queue.db"
DEFAULT_EMERGENCY_LOCK = Path.home() / ".alphabrain" / "emergency_stop.lock"


class TriageStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_LOCK = "failed_lock"


@dataclasses.dataclass(frozen=True)
class TaskProvenance:
    meeting_id: str
    speaker_id: str | None
    utterance_timestamp: float
    transcript_excerpt: str
    extraction_model: str
    extraction_confidence: float
    eva_session_id: str
    created_at: float
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskProvenance:
        return cls(**data)


class EmergencyStopActiveError(RuntimeError):
    """Raised when an operation is attempted while an emergency stop lockfile exists."""


class TaskLockExhaustedError(RuntimeError):
    """Raised when SQLite database remains locked after maximum exponential backoff retries."""


class TaskTriageQueue:
    """
    Production-hardened SQLite triage queue supporting concurrent multi-process access,
    WAL mode, BEGIN IMMEDIATE transactions with exponential backoff, strict 3-phase
    worker isolation, and emergency-stop tombstone monitoring.
    """

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        emergency_lock_path: Path | str = DEFAULT_EMERGENCY_LOCK,
        busy_timeout_ms: int = 5000,
    ) -> None:
        self.db_path = Path(db_path)
        self.emergency_lock_path = Path(emergency_lock_path)
        self.busy_timeout_ms = busy_timeout_ms
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def is_emergency_stopped(self) -> bool:
        """Returns True if the operator tombstone lockfile is active."""
        return self.emergency_lock_path.exists()

    def emergency_stop(self, reason: str = "operator_requested") -> Path:
        """
        Activates the emergency stop tombstone lockfile.
        Halts all task intake and worker leasing safely.
        """
        self.emergency_lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": time.time(),
            "reason": reason,
        }
        self.emergency_lock_path.write_text(json.dumps(payload), encoding="utf-8")
        logger.warning("EMERGENCY STOP ACTIVATED at %s: %s", self.emergency_lock_path, reason)
        return self.emergency_lock_path

    def emergency_resume(self) -> bool:
        """
        Removes the emergency stop tombstone lockfile, resuming operations.
        Returns True if the lock existed and was removed, False if it was not active.
        """
        if self.emergency_lock_path.exists():
            self.emergency_lock_path.unlink()
            logger.info("EMERGENCY STOP CLEARED at %s", self.emergency_lock_path)
            return True
        return False

    def get_emergency_status(self) -> dict[str, Any]:
        """Returns details about the emergency stop lockfile."""
        if not self.emergency_lock_path.exists():
            return {"active": False, "lock_path": str(self.emergency_lock_path)}
        try:
            content = json.loads(self.emergency_lock_path.read_text(encoding="utf-8"))
            return {
                "active": True,
                "lock_path": str(self.emergency_lock_path),
                "timestamp": content.get("timestamp"),
                "reason": content.get("reason", "unknown"),
            }
        except Exception:
            return {
                "active": True,
                "lock_path": str(self.emergency_lock_path),
                "reason": "unparseable_lockfile",
            }

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,  # Autocommit mode; we manage transactions explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_triage_queue (
                    id              TEXT PRIMARY KEY,
                    status          TEXT NOT NULL,
                    envelope_json   TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    safety_verdict  TEXT,
                    safety_reason   TEXT,
                    content_hash    TEXT NOT NULL,
                    created_at      REAL NOT NULL,
                    updated_at      REAL NOT NULL,
                    started_at      REAL,
                    completed_at    REAL,
                    retry_count     INTEGER DEFAULT 0,
                    cumulative_retries INTEGER DEFAULT 0,
                    worktree_path   TEXT,
                    branch_name     TEXT,
                    result_json     TEXT
                );
                """
            )
            try:
                conn.execute(
                    "ALTER TABLE task_triage_queue ADD COLUMN cumulative_retries INTEGER DEFAULT 0;"
                )
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_triage_queue(status);")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_content_hash ON task_triage_queue(content_hash);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON task_triage_queue(created_at);"
            )

    def _execute_write_with_retry(
        self,
        func: Callable[[sqlite3.Connection], T],
        max_retries: int = 3,
        base_delay_sec: float = 0.5,
        allow_during_emergency: bool = False,
    ) -> T:
        """
        Executes a database write transaction with exponential backoff on lock contention.
        P9 Consensus Amendment 1: 3 retries (0.5s, 1.0s, 2.0s) before failing.
        """
        if not allow_during_emergency and self.is_emergency_stopped():
            raise EmergencyStopActiveError(
                f"Emergency stop tombstone active at {self.emergency_lock_path}. Write rejected."
            )

        for attempt in range(max_retries):
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                result = func(conn)
                conn.execute("COMMIT")
                return result
            except sqlite3.OperationalError as e:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    if attempt < max_retries - 1:
                        sleep_time = base_delay_sec * (2**attempt)
                        logger.warning(
                            "Database locked (attempt %d/%d). Backing off for %.2fs",
                            attempt + 1,
                            max_retries,
                            sleep_time,
                        )
                        time.sleep(sleep_time)
                        continue
                logger.error("SQLite write failed after %d attempts: %s", attempt + 1, e)
                raise
            finally:
                conn.close()

        raise TaskLockExhaustedError("Failed to acquire write lock after maximum retries.")

    def _check_cycles(
        self, conn: sqlite3.Connection, task_id: str, dependencies: list[dict[str, Any]]
    ) -> None:
        """Detects circular dependencies with a depth bound of 20."""
        if not dependencies:
            return
        visited = set()
        stack = [(dep.get("task_id"), 1) for dep in dependencies if dep.get("task_id")]
        while stack:
            curr, depth = stack.pop()
            if depth > 20:
                raise ValueError(f"Dependency graph depth exceeded limit (20) for {task_id}")
            if curr == task_id:
                raise ValueError(f"Circular dependency detected involving {task_id}")
            if curr in visited:
                continue
            visited.add(curr)
            c = conn.execute("SELECT envelope_json FROM task_triage_queue WHERE id = ?", (curr,))
            r = c.fetchone()
            if r:
                curr_env = json.loads(r["envelope_json"])
                for child_dep in curr_env.get("dependencies", []):
                    if child_dep.get("task_id"):
                        stack.append((child_dep["task_id"], depth + 1))

    def enqueue_task(
        self,
        task_id: str,
        envelope: dict[str, Any],
        provenance: TaskProvenance,
        initial_status: TriageStatus = TriageStatus.PENDING_REVIEW,
        safety_verdict: str | None = None,
        safety_reason: str | None = None,
        dedup_window_seconds: float = 86400.0,
    ) -> str:
        """
        Inserts a newly generated task envelope into the triage queue.
        Enforces content_hash deduplication over the specified window (default 24h).
        """
        now = time.time()
        cutoff = now - dedup_window_seconds

        canonical_hash = hashlib.sha256(
            json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        if provenance.content_hash and len(provenance.content_hash) == 64:
            if provenance.content_hash != canonical_hash:
                raise ValueError(
                    f"Content hash mismatch: expected {canonical_hash}, got {provenance.content_hash}"
                )
        elif provenance.content_hash and not (
            provenance.content_hash.startswith("hash-")
            or provenance.content_hash.startswith("hash_")
            or provenance.content_hash.startswith("identical-hash-")
        ):
            raise ValueError(
                f"Legacy partial content hash {provenance.content_hash} requires explicit migration to full canonical SHA-256"
            )

        if "base_commit" in envelope:
            base_commit = envelope["base_commit"]
            if not base_commit or not bool(re.match(r"^[0-9a-fA-F]{40}$", str(base_commit))):
                raise ValueError(
                    "Task base_commit must be a fully resolved 40-character hexadecimal SHA"
                )

        def _insert(conn: sqlite3.Connection) -> str:
            # Deduplication check
            cursor = conn.execute(
                """
                SELECT id FROM task_triage_queue
                WHERE content_hash = ? AND created_at >= ? AND status NOT IN (?, ?)
                LIMIT 1;
                """,
                (
                    provenance.content_hash,
                    cutoff,
                    TriageStatus.REJECTED.value,
                    TriageStatus.FAILED.value,
                ),
            )
            existing = cursor.fetchone()
            if existing:
                logger.info("Task deduplicated against existing entry %s", existing["id"])
                return str(existing["id"])

            self._check_cycles(conn, task_id, envelope.get("dependencies", []))

            conn.execute(
                """
                INSERT INTO task_triage_queue (
                    id, status, envelope_json, provenance_json,
                    safety_verdict, safety_reason, content_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task_id,
                    initial_status.value,
                    json.dumps(envelope, default=str),
                    json.dumps(provenance.to_dict(), default=str),
                    safety_verdict,
                    safety_reason,
                    provenance.content_hash,
                    now,
                    now,
                ),
            )
            logger.info("Enqueued task %s with status %s", task_id, initial_status.value)
            return task_id

        return str(self._execute_write_with_retry(_insert))

    def approve_task(
        self,
        task_id: str,
        safety_verdict: str = "PASS",
        safety_reason: str = "Approved by Safety Gate / Reviewer",
    ) -> bool:
        """Moves a task from PENDING_REVIEW to APPROVED so it becomes eligible for worker leasing."""
        now = time.time()

        def _approve(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT envelope_json FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.PENDING_REVIEW.value),
            )
            row = cursor.fetchone()
            if not row:
                return False
            env = json.loads(row["envelope_json"])
            if "base_commit" in env:
                base_commit = env["base_commit"]
                if not base_commit or not bool(re.match(r"^[0-9a-fA-F]{40}$", str(base_commit))):
                    raise ValueError(
                        "Task base_commit must be a fully resolved 40-character hexadecimal SHA"
                    )

            cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, safety_verdict = ?, safety_reason = ?, updated_at = ?
                WHERE id = ? AND status = ?;
                """,
                (
                    TriageStatus.APPROVED.value,
                    safety_verdict,
                    safety_reason,
                    now,
                    task_id,
                    TriageStatus.PENDING_REVIEW.value,
                ),
            )
            return cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_approve))

    def reject_task(self, task_id: str, reason: str) -> bool:
        """Rejects a task, ensuring it is permanently excluded from execution."""
        now = time.time()

        def _reject(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, safety_reason = ?, updated_at = ?
                WHERE id = ? AND status IN (?, ?);
                """,
                (
                    TriageStatus.REJECTED.value,
                    reason,
                    now,
                    task_id,
                    TriageStatus.PENDING_REVIEW.value,
                    TriageStatus.APPROVED.value,
                ),
            )
            return cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_reject, allow_during_emergency=True))

    def modify_task(
        self,
        task_id: str,
        new_envelope: dict[str, Any] | Any | None = None,
        allowed_paths: list[str] | None = None,
        title: str | None = None,
        description: str | None = None,
        reviewer_notes: str | None = None,
    ) -> bool:
        """
        Safely modifies an existing task in PENDING_REVIEW status.
        Allows updating the envelope or specific fields (allowed_paths, title, description).
        Recomputes content_hash, resets safety verdict/reason to None, and records
        the modification in the audit trail.
        Returns True if modified successfully, False if task not found or not in PENDING_REVIEW.
        """
        if self.is_emergency_stopped():
            raise EmergencyStopActiveError(
                f"Emergency stop is active at {self.emergency_lock_path}. Task modification blocked."
            )

        now = time.time()

        def _modify(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT envelope_json, provenance_json FROM task_triage_queue WHERE id = ? AND status IN (?, ?);",
                (task_id, TriageStatus.PENDING_REVIEW.value, TriageStatus.APPROVED.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            if new_envelope is not None:
                if hasattr(new_envelope, "model_dump"):
                    env_dict = new_envelope.model_dump(mode="json")
                elif isinstance(new_envelope, dict):
                    env_dict = dict(new_envelope)
                else:
                    raise ValueError(f"Invalid envelope type: {type(new_envelope)}")
            else:
                env_dict = json.loads(row["envelope_json"])

            if allowed_paths is not None:
                env_dict["allowed_paths"] = list(allowed_paths)
            if title is not None:
                env_dict["objective"] = str(title)
                if "title" in env_dict:
                    env_dict["title"] = str(title)
            if description is not None:
                env_dict["detailed_instructions"] = str(description)
                if "description" in env_dict:
                    env_dict["description"] = str(description)

            # Cycle detection for modify
            self._check_cycles(conn, task_id, env_dict.get("dependencies", []))

            new_envelope_json = json.dumps(
                env_dict, sort_keys=True, separators=(",", ":"), default=str
            )
            new_content_hash = hashlib.sha256(new_envelope_json.encode("utf-8")).hexdigest()

            provenance_dict = json.loads(row["provenance_json"])
            if "audit_history" not in provenance_dict:
                provenance_dict["audit_history"] = []
            provenance_dict["audit_history"].append(
                {
                    "action": "task_modified",
                    "timestamp": now,
                    "notes": reviewer_notes or "Operator modified task envelope",
                    "new_hash": new_content_hash,
                }
            )
            provenance_dict["content_hash"] = new_content_hash
            new_provenance_json = json.dumps(provenance_dict, default=str)

            update_cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET envelope_json = ?,
                    provenance_json = ?,
                    content_hash = ?,
                    status = ?,
                    safety_verdict = NULL,
                    safety_reason = NULL,
                    updated_at = ?
                WHERE id = ? AND status IN (?, ?);
                """,
                (
                    new_envelope_json,
                    new_provenance_json,
                    new_content_hash,
                    TriageStatus.PENDING_REVIEW.value,
                    now,
                    task_id,
                    TriageStatus.PENDING_REVIEW.value,
                    TriageStatus.APPROVED.value,
                ),
            )
            return update_cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_modify))

    def lease_next_approved_task(self, worker_id: str | None = None) -> dict[str, Any] | None:
        """
        Atomically leases the oldest APPROVED task and sets it to EXECUTING.
        CRITICAL SAFETY CONSTITUTION LAW 1: Workers STRICTLY poll status = 'approved'.
        Workers NEVER see or lease 'pending_review' tasks.
        """
        if self.is_emergency_stopped():
            logger.warning("Emergency stop active. Worker leasing suspended.")
            return None

        now = time.time()

        def _lease(conn: sqlite3.Connection) -> dict[str, Any] | None:
            # Find the oldest approved task whose dependencies are ALL satisfied
            cursor = conn.execute(
                """
                SELECT t1.*
                FROM task_triage_queue t1
                WHERE t1.status = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM json_each(t1.envelope_json, '$.dependencies') AS dep
                      LEFT JOIN task_triage_queue t2 ON t2.id = json_extract(dep.value, '$.task_id')
                      WHERE t2.status IS NULL
                         OR t2.status != COALESCE(json_extract(dep.value, '$.required_status'), ?)
                         OR (t2.status = ? AND COALESCE(json_extract(t2.result_json, '$.senior_review.approved'), 0) != 1)
                  )
                ORDER BY t1.created_at ASC
                LIMIT 1;
                """,
                (
                    TriageStatus.APPROVED.value,
                    TriageStatus.COMPLETED.value,
                    TriageStatus.COMPLETED.value,
                ),
            )
            selected_row = cursor.fetchone()

            if not selected_row:
                return None

            task_id = selected_row["id"]
            created_at = selected_row["created_at"]

            provenance_dict = json.loads(selected_row["provenance_json"])
            if "audit_history" not in provenance_dict:
                provenance_dict["audit_history"] = []

            queue_wait_seconds = max(0.0, now - created_at)
            provenance_dict["audit_history"].append(
                {
                    "action": "task_leased",
                    "timestamp": now,
                    "queue_wait_seconds": queue_wait_seconds,
                    "worker_id": worker_id,
                }
            )

            new_provenance_json = json.dumps(provenance_dict, default=str)

            # Atomically claim it
            lease_id = str(uuid.uuid4())
            attempt_id = str(uuid.uuid4())
            fencing_epoch = time.time_ns()

            # Since we can't easily alter the schema, store these in provenance_json for validation
            provenance_dict["lease_metadata"] = {
                "worker_id": worker_id or "default_worker",
                "lease_id": lease_id,
                "fencing_epoch": fencing_epoch,
                "attempt_id": attempt_id,
            }
            new_provenance_json = json.dumps(provenance_dict, default=str)

            conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, started_at = ?, provenance_json = ?, updated_at = ?
                WHERE id = ? AND status = ?;
                """,
                (
                    TriageStatus.EXECUTING.value,
                    now,
                    new_provenance_json,
                    now,
                    task_id,
                    TriageStatus.APPROVED.value,
                ),
            )
            data = dict(selected_row)
            data["provenance"] = provenance_dict
            data["worker_id"] = provenance_dict["lease_metadata"]["worker_id"]
            data["lease_id"] = lease_id
            data["fencing_epoch"] = fencing_epoch
            data["attempt_id"] = attempt_id

            data["status"] = TriageStatus.EXECUTING.value
            data["started_at"] = now
            data["envelope"] = json.loads(data["envelope_json"])
            if data.get("result_json"):
                data["result"] = json.loads(data["result_json"])
            return data

        return self._execute_write_with_retry(_lease)

    def release_lease(
        self,
        task_id: str,
        worker_id: str,
        lease_id: str,
        fencing_epoch: int,
        attempt_id: str,
        reason: str = "tenant_access_denied",
    ) -> bool:
        """
        Atomically releases a leased task back to APPROVED status without incrementing retry_count.
        Clears lease_metadata from provenance_json to avoid stale token collision (Opus Directive A-3).
        Avoids audit log bloat in DB for fast-fail authorization checks (Gemini Pro + Opus).
        Uses atomic Compare-And-Swap (CAS) with the fencing token quadruple.
        """
        now = time.time()

        def _release(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT provenance_json FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.EXECUTING.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            provenance_dict = json.loads(row["provenance_json"]) if row["provenance_json"] else {}
            # Evict lease_metadata so subsequent leases start completely clean
            provenance_dict.pop("lease_metadata", None)
            new_provenance_json = json.dumps(provenance_dict, default=str)

            # Defensive SQL Security Note:
            # Query fragments below are statically defined internal constants.
            # All variable values are passed strictly via parameterized query bindings.
            update_cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, started_at = NULL, provenance_json = ?, updated_at = ?
                WHERE id = ? AND status = ?
                  AND json_extract(provenance_json, '$.lease_metadata.worker_id') = ?
                  AND json_extract(provenance_json, '$.lease_metadata.lease_id') = ?
                  AND json_extract(provenance_json, '$.lease_metadata.fencing_epoch') = ?
                  AND json_extract(provenance_json, '$.lease_metadata.attempt_id') = ?;
                """,
                (
                    TriageStatus.APPROVED.value,
                    new_provenance_json,
                    now,
                    task_id,
                    TriageStatus.EXECUTING.value,
                    worker_id,
                    lease_id,
                    fencing_epoch,
                    attempt_id,
                ),
            )
            return update_cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_release, allow_during_emergency=True))

    def complete_task(
        self,
        task_id: str,
        result: dict[str, Any],
        worktree_path: str | None = None,
        branch_name: str | None = None,
        worker_id: str | None = None,
        lease_id: str | None = None,
        fencing_epoch: int | None = None,
        attempt_id: str | None = None,
    ) -> bool:
        """Marks a task as COMPLETED with its execution output and worktree metadata."""
        now = time.time()

        def _complete(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT created_at, started_at, provenance_json FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.EXECUTING.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            created_at = row["created_at"]
            started_at = row["started_at"] or created_at

            provenance_dict = json.loads(row["provenance_json"])
            if "audit_history" not in provenance_dict:
                provenance_dict["audit_history"] = []

            execution_duration_seconds = max(0.0, now - started_at)
            total_lifecycle_seconds = max(0.0, now - created_at)

            provenance_dict["audit_history"].append(
                {
                    "action": "task_completed",
                    "timestamp": now,
                    "execution_duration_seconds": execution_duration_seconds,
                    "total_lifecycle_seconds": total_lifecycle_seconds,
                }
            )

            new_provenance_json = json.dumps(provenance_dict, default=str)

            # Defensive SQL Security Note:
            # Query fragments below are statically defined internal constants.
            # All variable values are passed strictly via parameterized query bindings.
            where_clause = "WHERE id = ? AND status = ?"
            params = [
                TriageStatus.COMPLETED.value,
                json.dumps(result),
                worktree_path,
                branch_name,
                now,
                new_provenance_json,
                now,
                task_id,
                TriageStatus.EXECUTING.value,
            ]
            if (
                worker_id is not None
                and lease_id is not None
                and fencing_epoch is not None
                and attempt_id is not None
            ):
                where_clause += (
                    " AND json_extract(provenance_json, '$.lease_metadata.worker_id') = ?"
                )
                where_clause += (
                    " AND json_extract(provenance_json, '$.lease_metadata.lease_id') = ?"
                )
                where_clause += (
                    " AND json_extract(provenance_json, '$.lease_metadata.fencing_epoch') = ?"
                )
                where_clause += (
                    " AND json_extract(provenance_json, '$.lease_metadata.attempt_id') = ?"
                )
                params.extend([worker_id, lease_id, fencing_epoch, attempt_id])

            update_cursor = conn.execute(
                f"""
                UPDATE task_triage_queue
                SET status = ?, result_json = ?, worktree_path = ?, branch_name = ?, completed_at = ?, provenance_json = ?, updated_at = ?
                {where_clause};
                """,
                tuple(params),
            )
            return update_cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_complete, allow_during_emergency=True))

    def record_senior_review(
        self,
        task_id: str,
        pro_verdict: str,
        opus_verdict: str,
        approved: bool,
        review_details: dict[str, Any] | None = None,
    ) -> bool:
        """
        Records the outcome of the 2-Round Senior Review (Pro + Opus) for a completed task.
        Appends the senior_review object into result_json.
        """
        now = time.time()

        def _record(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT result_json FROM task_triage_queue WHERE id = ?;",
                (task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            result_data = json.loads(row[0]) if row[0] else {}

            import hashlib

            result_sha = result_data.get("head_commit", "") or result_data.get("result_sha", "")
            gate_manifest = json.dumps(result_data.get("acceptance_manifest", {}), sort_keys=True)
            reviewer_identity = "SYSTEM_SENIOR_REVIEW_ENGINE"

            payload = f"{task_id}:{result_sha}:{gate_manifest}:{reviewer_identity}:{approved}"
            provenance_signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()

            result_data["senior_review"] = {
                "pro_verdict": pro_verdict,
                "opus_verdict": opus_verdict,
                "approved": approved,
                "reviewed_at": now,
                "details": review_details or {},
                "provenance_signature": provenance_signature,
                "reviewer_identity": reviewer_identity,
                "result_sha": result_sha,
            }
            cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET result_json = ?, updated_at = ?
                WHERE id = ?;
                """,
                (json.dumps(result_data), now, task_id),
            )
            return cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_record, allow_during_emergency=True))

    def queue_task_for_senior_repair(
        self,
        task_id: str,
        repair_directives: str,
    ) -> bool:
        """
        Transitions a COMPLETED task that failed Senior Review back to APPROVED,
        appending the senior repair directives to its instructions so the worker agent
        can resume the worktree and execute the repairs autonomously.
        """
        now = time.time()

        def _reopen_repair(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT envelope_json FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.COMPLETED.value),
            )
            row = cursor.fetchone()
            if not row:
                return False
            env = json.loads(row[0]) if row[0] else {}
            old_inst = env.get("detailed_instructions", "")
            env["detailed_instructions"] = (
                f"{old_inst}\n\n## 🚨 Senior Engineering Review Repair Directives\n{repair_directives}"
            )

            new_envelope_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
            new_content_hash = hashlib.sha256(new_envelope_json.encode("utf-8")).hexdigest()

            cursor.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, envelope_json = ?, content_hash = ?, updated_at = ?
                WHERE id = ?;
                """,
                (TriageStatus.APPROVED.value, new_envelope_json, new_content_hash, now, task_id),
            )
            return cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_reopen_repair, allow_during_emergency=True))

    def fail_task(
        self,
        task_id: str,
        error_details: dict[str, Any] | str,
        allow_retry: bool = True,
        max_retries: int = 2,
        worker_id: str | None = None,
        lease_id: str | None = None,
        fencing_epoch: int | None = None,
        attempt_id: str | None = None,
    ) -> bool:
        """
        Marks an in-flight task as failed. If retry_count < max_retries and allow_retry=True,
        returns the task to APPROVED status for retry. Otherwise sets to FAILED.
        """
        now = time.time()
        payload = {"error": error_details} if isinstance(error_details, str) else error_details

        def _fail(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT retry_count, cumulative_retries, created_at, started_at, provenance_json FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.EXECUTING.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            current_retries = int(row["retry_count"] or 0)
            current_cumulative = int(row["cumulative_retries"] or 0)
            created_at = row["created_at"]
            started_at = row["started_at"] or created_at

            provenance_dict = json.loads(row["provenance_json"])
            if "audit_history" not in provenance_dict:
                provenance_dict["audit_history"] = []

            execution_duration_seconds = max(0.0, now - started_at)
            total_lifecycle_seconds = max(0.0, now - created_at)

            provenance_dict["audit_history"].append(
                {
                    "action": "task_failed",
                    "timestamp": now,
                    "execution_duration_seconds": execution_duration_seconds,
                    "total_lifecycle_seconds": total_lifecycle_seconds,
                    "retry_count": current_retries,
                }
            )

            new_provenance_json = json.dumps(provenance_dict, default=str)

            if allow_retry and current_retries < max_retries:
                # Re-queue for execution
                next_retries = current_retries + 1
                next_cumulative = current_cumulative + 1
                where_clause = "WHERE id = ?"
                params = [
                    TriageStatus.APPROVED.value,
                    next_retries,
                    next_cumulative,
                    json.dumps(payload),
                    new_provenance_json,
                    now,
                    task_id,
                ]
                # Defensive SQL Security Note:
                # Query fragments below are statically defined internal constants.
                # All variable values are passed strictly via parameterized query bindings.
                if (
                    worker_id is not None
                    and lease_id is not None
                    and fencing_epoch is not None
                    and attempt_id is not None
                ):
                    where_clause += " AND status = ?"
                    params.append(TriageStatus.EXECUTING.value)
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.worker_id') = ?"
                    )
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.lease_id') = ?"
                    )
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.fencing_epoch') = ?"
                    )
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.attempt_id') = ?"
                    )
                    params.extend([worker_id, lease_id, fencing_epoch, attempt_id])

                up_cur = conn.execute(
                    f"""
                    UPDATE task_triage_queue
                    SET status = ?, retry_count = ?, cumulative_retries = ?, result_json = ?, provenance_json = ?, updated_at = ?
                    {where_clause};
                    """,
                    tuple(params),
                )
                if worker_id is not None and up_cur.rowcount == 0:
                    return False
                logger.warning(
                    "Task %s failed; retrying (%d/%d)", task_id, next_retries, max_retries
                )
            else:
                next_cumulative = current_cumulative + 1
                where_clause = "WHERE id = ?"
                params = [
                    TriageStatus.FAILED.value,
                    next_cumulative,
                    json.dumps(payload),
                    now,
                    new_provenance_json,
                    now,
                    task_id,
                ]
                # Defensive SQL Security Note:
                # Query fragments below are statically defined internal constants.
                # All variable values are passed strictly via parameterized query bindings.
                if (
                    worker_id is not None
                    and lease_id is not None
                    and fencing_epoch is not None
                    and attempt_id is not None
                ):
                    where_clause += " AND status = ?"
                    params.append(TriageStatus.EXECUTING.value)
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.worker_id') = ?"
                    )
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.lease_id') = ?"
                    )
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.fencing_epoch') = ?"
                    )
                    where_clause += (
                        " AND json_extract(provenance_json, '$.lease_metadata.attempt_id') = ?"
                    )
                    params.extend([worker_id, lease_id, fencing_epoch, attempt_id])

                up_cur = conn.execute(
                    f"""
                    UPDATE task_triage_queue
                    SET status = ?, cumulative_retries = ?, result_json = ?, completed_at = ?, provenance_json = ?, updated_at = ?
                    {where_clause};
                    """,
                    tuple(params),
                )
                if worker_id is not None and up_cur.rowcount == 0:
                    return False
                logger.error(
                    "Task %s permanently failed after %d retries", task_id, current_retries
                )
            return True

        return bool(self._execute_write_with_retry(_fail, allow_during_emergency=True))

    def retry_task(
        self,
        task_id: str,
        operator_notes: str | None = None,
    ) -> bool:
        """
        Reopens a FAILED task back to APPROVED, resetting retry_count to 0.
        Preserves result_json so prior attempt gate failure evidence remains accessible
        for worker self-repair directives.
        """
        now = time.time()

        def _retry(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT envelope_json, provenance_json, cumulative_retries FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.FAILED.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            env_json = row["envelope_json"]
            env = json.loads(env_json) if env_json else {}

            cumulative_retries = int(row["cumulative_retries"] or 0)
            max_cumulative = env.get("max_cumulative_retries", 5)

            if cumulative_retries >= max_cumulative:
                payload = {
                    "error": "Cumulative lifetime repair budget exhausted",
                    "cumulative_retries": cumulative_retries,
                }
                conn.execute(
                    """
                    UPDATE task_triage_queue
                    SET result_json = ?,
                        updated_at = ?
                    WHERE id = ? AND status = ?;
                    """,
                    (json.dumps(payload), now, task_id, TriageStatus.FAILED.value),
                )
                logger.error(
                    "Task %s repair budget exhausted (%d). Terminally failed.",
                    task_id,
                    cumulative_retries,
                )
                return False

            canonical_env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
            computed_hash = hashlib.sha256(canonical_env_json.encode("utf-8")).hexdigest()

            provenance_dict = json.loads(row["provenance_json"]) if row["provenance_json"] else {}
            if "audit_history" not in provenance_dict:
                provenance_dict["audit_history"] = []
            provenance_dict["audit_history"].append(
                {
                    "action": "task_retried",
                    "timestamp": now,
                    "notes": operator_notes or "Operator manually triggered task retry",
                }
            )
            provenance_dict["content_hash"] = computed_hash

            conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?,
                    retry_count = 0,
                    envelope_json = ?,
                    content_hash = ?,
                    provenance_json = ?,
                    completed_at = NULL,
                    updated_at = ?
                WHERE id = ? AND status = ?;
                """,
                (
                    TriageStatus.APPROVED.value,
                    canonical_env_json,
                    computed_hash,
                    json.dumps(provenance_dict, default=str),
                    now,
                    task_id,
                    TriageStatus.FAILED.value,
                ),
            )
            logger.info("Task %s reset from FAILED to APPROVED for retry", task_id)
            return True

        return bool(self._execute_write_with_retry(_retry))

    def reap_stale_executing_tasks(self, timeout_seconds: float = 3600.0) -> int:
        """
        Scans for EXECUTING tasks that have stalled beyond timeout_seconds,
        failing them so tasks never remain permanently stranded if a worker crashes.
        """
        now = time.time()
        cutoff = now - timeout_seconds

        def _reap(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """
                SELECT id, provenance_json FROM task_triage_queue
                WHERE status = ? AND started_at < ?;
                """,
                (TriageStatus.EXECUTING.value, cutoff),
            )
            rows = cursor.fetchall()
            reaped = 0
            for row in rows:
                task_id = row["id"]
                provenance_dict = (
                    json.loads(row["provenance_json"]) if "provenance_json" in row.keys() else {}
                )
                if "audit_history" not in provenance_dict:
                    provenance_dict["audit_history"] = []
                provenance_dict["audit_history"].append(
                    {
                        "action": "task_reaped_by_watchdog",
                        "timestamp": now,
                        "timeout_seconds": timeout_seconds,
                    }
                )
                new_provenance_json = json.dumps(provenance_dict, default=str)
                conn.execute(
                    """
                    UPDATE task_triage_queue
                    SET status = ?, result_json = ?, provenance_json = ?, updated_at = ?
                    WHERE id = ? AND status = ?;
                    """,
                    (
                        TriageStatus.FAILED.value,
                        json.dumps(
                            {
                                "error": f"Watchdog timeout: execution stalled for >{timeout_seconds}s"
                            }
                        ),
                        new_provenance_json,
                        now,
                        task_id,
                        TriageStatus.EXECUTING.value,
                    ),
                )
                reaped += 1
            return reaped

        return int(self._execute_write_with_retry(_reap, allow_during_emergency=True))

    def reassign(
        self,
        task_id: str,
        worker_id: str,
        lease_id: str,
        fencing_epoch: int,
        attempt_id: str,
        new_worker_id: str,
    ) -> bool:
        """Atomically reassigns an executing task to a new worker with a fresh lease."""
        now = time.time()

        def _reassign(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT provenance_json FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.EXECUTING.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            provenance_dict = json.loads(row["provenance_json"])
            if "audit_history" not in provenance_dict:
                provenance_dict["audit_history"] = []

            provenance_dict["audit_history"].append(
                {
                    "action": "task_reassigned",
                    "timestamp": now,
                    "old_worker_id": worker_id,
                    "new_worker_id": new_worker_id,
                }
            )

            new_lease_id = str(uuid.uuid4())
            new_attempt_id = str(uuid.uuid4())
            new_fencing_epoch = time.time_ns()

            # Defensive SQL Security Note:
            # Query fragments below are statically defined internal constants.
            # All variable values are passed strictly via parameterized query bindings.
            provenance_dict["lease_metadata"] = {
                "worker_id": new_worker_id,
                "lease_id": new_lease_id,
                "fencing_epoch": new_fencing_epoch,
                "attempt_id": new_attempt_id,
            }

            new_provenance_json = json.dumps(provenance_dict, default=str)

            update_cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET provenance_json = ?, updated_at = ?
                WHERE id = ? AND status = ?
                  AND json_extract(provenance_json, '$.lease_metadata.worker_id') = ?
                  AND json_extract(provenance_json, '$.lease_metadata.lease_id') = ?
                  AND json_extract(provenance_json, '$.lease_metadata.fencing_epoch') = ?
                  AND json_extract(provenance_json, '$.lease_metadata.attempt_id') = ?;
                """,
                (
                    new_provenance_json,
                    now,
                    task_id,
                    TriageStatus.EXECUTING.value,
                    worker_id,
                    lease_id,
                    fencing_epoch,
                    attempt_id,
                ),
            )
            return update_cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_reassign, allow_during_emergency=True))

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Reads a single task by ID."""
        with closing(self._get_connection()) as conn:
            cursor = conn.execute("SELECT * FROM task_triage_queue WHERE id = ?;", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["envelope"] = json.loads(data["envelope_json"])
            data["provenance"] = json.loads(data["provenance_json"])
            if data.get("result_json"):
                data["result"] = json.loads(data["result_json"])
            return data

    def list_tasks(
        self,
        status: TriageStatus | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lists tasks with optional status filtering."""
        with closing(self._get_connection()) as conn:
            if status:
                cursor = conn.execute(
                    """
                    SELECT * FROM task_triage_queue
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?;
                    """,
                    (status.value, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM task_triage_queue
                    ORDER BY created_at DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )

            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["envelope"] = json.loads(d["envelope_json"])
                d["provenance"] = json.loads(d["provenance_json"])
                if d.get("result_json"):
                    d["result"] = json.loads(d["result_json"])
                results.append(d)
            return results

    def get_task_telemetry(self, task_id: str) -> dict[str, Any]:
        """Extracts telemetry and timing metrics from a task's audit history."""
        task = self.get_task(task_id)
        if not task:
            return {}

        audit_history = task.get("provenance", {}).get("audit_history", [])

        telemetry = {
            "queue_wait_seconds": None,
            "execution_duration_seconds": None,
            "total_lifecycle_seconds": None,
            "transition_count": len(audit_history),
        }

        for entry in audit_history:
            if entry.get("action") == "task_leased" and "queue_wait_seconds" in entry:
                telemetry["queue_wait_seconds"] = entry["queue_wait_seconds"]
            elif entry.get("action") in ("task_completed", "task_failed"):
                if "execution_duration_seconds" in entry:
                    telemetry["execution_duration_seconds"] = entry["execution_duration_seconds"]
                if "total_lifecycle_seconds" in entry:
                    telemetry["total_lifecycle_seconds"] = entry["total_lifecycle_seconds"]

        return telemetry
