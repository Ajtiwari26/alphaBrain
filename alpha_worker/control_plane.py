"""Outbound-only control-plane client and encrypted crash-safe event spool."""

import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken

from alpha_protocol import TaskEnvelope, TaskResult, WorkerHealthReport, WorkerRegistration


class ControlPlaneUnavailable(RuntimeError):
    """Raised when remote control plane cannot safely confirm an operation."""


class ControlPlaneProtocolError(RuntimeError):
    """Raised when control plane returns invalid or unexpected data."""


@dataclass(frozen=True)
class LeasedTask:
    lease_token: str
    task: TaskEnvelope


class DurableEventSpool:
    """Fernet-encrypted per-event files, replayed only after successful acknowledgement."""

    def __init__(self, directory: Path, fernet_key: str | bytes) -> None:
        if not fernet_key:
            raise ValueError("Worker spool encryption key is required")
        try:
            self._fernet = Fernet(
                fernet_key.encode() if isinstance(fernet_key, str) else fernet_key
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Worker spool encryption key is invalid") from exc
        self.directory = directory.expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self._last_sequence = self._find_last_sequence()

    def _find_last_sequence(self) -> int:
        sequences = []
        for path in self.directory.glob("*.event"):
            prefix = path.name.partition("_")[0]
            if prefix.isdigit():
                sequences.append(int(prefix))
        return max(sequences, default=0)

    def _next_sequence(self) -> int:
        self._last_sequence = max(self._last_sequence + 1, time.time_ns())
        return self._last_sequence

    def enqueue(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        coalesce: bool = False,
    ) -> Path:
        sequence = self._next_sequence()
        event = {
            "event_id": f"sp_{uuid.uuid4().hex}",
            "sequence": sequence,
            "event_type": event_type,
            "payload": payload,
        }
        encrypted = self._fernet.encrypt(json.dumps(event, separators=(",", ":")).encode())
        destination = self.directory / f"{sequence:020d}_{event['event_id']}.event"
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
        if coalesce:
            for stale in self.pending():
                if stale == destination:
                    continue
                try:
                    old_event = self.read(stale)
                except ControlPlaneProtocolError:
                    continue
                if old_event.get("event_type") == event_type:
                    stale.unlink()
        return destination

    def pending(self) -> list[Path]:
        return sorted(self.directory.glob("*.event"), key=lambda path: path.name)

    def read(self, path: Path) -> dict[str, Any]:
        try:
            raw = self._fernet.decrypt(path.read_bytes())
            parsed = json.loads(raw)
        except (InvalidToken, OSError, ValueError, json.JSONDecodeError) as exc:
            raise ControlPlaneProtocolError(f"Unreadable worker spool event: {path.name}") from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("event_type"), str):
            raise ControlPlaneProtocolError(f"Invalid worker spool event: {path.name}")
        return parsed

    async def replay(
        self,
        deliver: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> int:
        delivered = 0
        for path in self.pending():
            event = self.read(path)
            await deliver(event["event_type"], event["payload"])
            path.unlink()
            delivered += 1
        return delivered


class ControlPlaneClient:
    """Authenticated, outbound-only worker API client; never touches server database."""

    def __init__(
        self,
        base_url: str,
        worker_token: str,
        identity_token: str,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Worker control-plane URL must be HTTP(S)")
        if not worker_token or not identity_token:
            raise ValueError("Worker control-plane credentials are required")
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {worker_token}",
            "X-Alpha-Worker-Identity": identity_token,
        }
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def register(self, registration: WorkerRegistration) -> None:
        await self._request("POST", "/api/workers/register", registration.model_dump(mode="json"))

    async def report_health(self, report: WorkerHealthReport) -> None:
        await self._request(
            "POST",
            f"/api/workers/{report.worker_id}/health",
            report.model_dump(mode="json"),
        )

    async def lease_next(
        self, worker_id: str, preferred_agent: str | None = None
    ) -> LeasedTask | None:
        payload = {"worker_id": worker_id}
        if preferred_agent:
            payload["preferred_agent"] = preferred_agent
        response = await self._request("POST", "/api/tasks/lease", payload)
        if response.get("status") == "no_tasks_available":
            return None
        if response.get("status") != "leased":
            raise ControlPlaneProtocolError("Unexpected lease response")
        try:
            return LeasedTask(
                lease_token=str(response["lease_token"]),
                task=TaskEnvelope.model_validate(response["task"]),
            )
        except (KeyError, ValueError) as exc:
            raise ControlPlaneProtocolError("Invalid lease response") from exc

    async def heartbeat(self, task_id: str, lease_token: str) -> str:
        response = await self._request(
            "POST", f"/api/tasks/{task_id}/heartbeat", {"lease_token": lease_token}
        )
        status = response.get("status")
        if status not in {"heartbeat_recorded", "cancel_requested", "ok"}:
            raise ControlPlaneProtocolError("Unexpected heartbeat response")
        return str(status)

    async def submit_result(self, result: TaskResult, lease_token: str) -> None:
        await self._request(
            "POST",
            f"/api/tasks/{result.task_id}/result",
            {"lease_token": lease_token, "result": result.model_dump(mode="json")},
        )

    async def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            raise ControlPlaneUnavailable(
                f"Control plane unavailable: {exc.__class__.__name__}"
            ) from exc
        if response.status_code >= 500:
            raise ControlPlaneUnavailable(f"Control plane server error: {response.status_code}")
        if response.status_code >= 400:
            raise ControlPlaneProtocolError(
                f"Control plane rejected request: {response.status_code}"
            )
        try:
            parsed = response.json()
        except ValueError as exc:
            raise ControlPlaneProtocolError("Control plane returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ControlPlaneProtocolError("Control plane response must be object")
        return parsed
