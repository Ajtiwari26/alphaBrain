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
import sqlite3
import time
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
                    worktree_path   TEXT,
                    branch_name     TEXT,
                    result_json     TEXT
                );
                """
            )
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
    ) -> T:
        """
        Executes a database write transaction with exponential backoff on lock contention.
        P9 Consensus Amendment 1: 3 retries (0.5s, 1.0s, 2.0s) before failing.
        """
        if self.is_emergency_stopped():
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

        return bool(self._execute_write_with_retry(_reject))

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

            new_envelope_json = json.dumps(env_dict, default=str)
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

    def lease_next_approved_task(self) -> dict[str, Any] | None:
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
            # Find the oldest approved task
            cursor = conn.execute(
                """
                SELECT * FROM task_triage_queue
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (TriageStatus.APPROVED.value,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            task_id = row["id"]
            # Atomically claim it
            conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, started_at = ?, updated_at = ?
                WHERE id = ? AND status = ?;
                """,
                (
                    TriageStatus.EXECUTING.value,
                    now,
                    now,
                    task_id,
                    TriageStatus.APPROVED.value,
                ),
            )
            data = dict(row)
            data["status"] = TriageStatus.EXECUTING.value
            data["started_at"] = now
            data["envelope"] = json.loads(data["envelope_json"])
            data["provenance"] = json.loads(data["provenance_json"])
            return data

        return self._execute_write_with_retry(_lease)

    def complete_task(
        self,
        task_id: str,
        result: dict[str, Any],
        worktree_path: str | None = None,
        branch_name: str | None = None,
    ) -> bool:
        """Marks a task as COMPLETED with its execution output and worktree metadata."""
        now = time.time()

        def _complete(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """
                UPDATE task_triage_queue
                SET status = ?, result_json = ?, worktree_path = ?, branch_name = ?, completed_at = ?, updated_at = ?
                WHERE id = ? AND status = ?;
                """,
                (
                    TriageStatus.COMPLETED.value,
                    json.dumps(result),
                    worktree_path,
                    branch_name,
                    now,
                    now,
                    task_id,
                    TriageStatus.EXECUTING.value,
                ),
            )
            return cursor.rowcount > 0

        return bool(self._execute_write_with_retry(_complete))

    def fail_task(
        self,
        task_id: str,
        error_details: dict[str, Any],
        allow_retry: bool = True,
        max_retries: int = 2,
    ) -> bool:
        """
        Marks an in-flight task as failed. If retry_count < max_retries and allow_retry=True,
        returns the task to APPROVED status for retry. Otherwise sets to FAILED.
        """
        now = time.time()

        def _fail(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "SELECT retry_count FROM task_triage_queue WHERE id = ? AND status = ?;",
                (task_id, TriageStatus.EXECUTING.value),
            )
            row = cursor.fetchone()
            if not row:
                return False

            current_retries = int(row["retry_count"] or 0)
            if allow_retry and current_retries < max_retries:
                # Re-queue for execution
                next_retries = current_retries + 1
                conn.execute(
                    """
                    UPDATE task_triage_queue
                    SET status = ?, retry_count = ?, result_json = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        TriageStatus.APPROVED.value,
                        next_retries,
                        json.dumps(error_details),
                        now,
                        task_id,
                    ),
                )
                logger.warning(
                    "Task %s failed; retrying (%d/%d)", task_id, next_retries, max_retries
                )
            else:
                conn.execute(
                    """
                    UPDATE task_triage_queue
                    SET status = ?, result_json = ?, completed_at = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        TriageStatus.FAILED.value,
                        json.dumps(error_details),
                        now,
                        now,
                        task_id,
                    ),
                )
                logger.error(
                    "Task %s permanently failed after %d retries", task_id, current_retries
                )
            return True

        return bool(self._execute_write_with_retry(_fail))

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
