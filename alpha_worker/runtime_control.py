"""Durable local worker pause/kill control, safe across daemon restarts."""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerControlState:
    paused: bool = False
    reason: str = ""


class WorkerControlStore:
    """Atomic 0600 worker control file; never stores credentials or task payloads."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)
        self.path = self.state_dir / "control.json"

    def read(self) -> WorkerControlState:
        if not self.path.exists():
            return WorkerControlState()
        try:
            payload = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Worker control state is unreadable") from exc
        if (
            not isinstance(payload, dict)
            or "paused" not in payload
            or not isinstance(payload["paused"], bool)
        ):
            raise RuntimeError("Worker control state is invalid")
        reason = payload.get("reason", "")
        if not isinstance(reason, str):
            raise RuntimeError("Worker control reason is invalid")
        return WorkerControlState(paused=payload["paused"], reason=reason)

    def pause(self, reason: str = "operator_requested") -> WorkerControlState:
        return self._write(WorkerControlState(paused=True, reason=reason))

    def resume(self) -> WorkerControlState:
        return self._write(WorkerControlState())

    def _write(self, state: WorkerControlState) -> WorkerControlState:
        temporary = self.path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump(
                {"paused": state.paused, "reason": state.reason}, output, separators=(",", ":")
            )
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)
        return state
