"""Outbound-only control-plane client and encrypted crash-safe event spool."""

import asyncio
import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
from cryptography.fernet import Fernet, InvalidToken

from alpha_protocol import (
    AppendCheckpointRequest,
    ResumeDecisionRequest,
    ResumeDecisionResponse,
    TaskCheckpoint,
    TaskEnvelope,
    TaskResult,
    WorkerHealthReport,
    WorkerRegistration,
)


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
                    stale.unlink(missing_ok=True)
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
            path.unlink(missing_ok=True)
            delivered += 1
        return delivered


class ControlPlaneClient:
    """Authenticated, outbound-only worker API client; never touches server database."""

    def __init__(
        self,
        base_url: str,
        worker_id: str,
        worker_token: str,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Worker control-plane URL must be HTTP(S)")
        if not worker_token or not worker_id:
            raise ValueError("Worker control-plane credentials are required")
        self.base_url = base_url.rstrip("/")
        self._worker_id = worker_id
        self._worker_token = worker_token
        self._identity_token: str | None = None
        self._identity_expires_at: int = 0
        self._refresh_lock = asyncio.Lock()

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _ensure_identity(self, force_refresh: bool = False) -> str:
        async with self._refresh_lock:
            now = time.time()
            if (
                not force_refresh
                and self._identity_token
                and now < (self._identity_expires_at - 60)
            ):
                return self._identity_token

            try:
                response = await self._client.post(
                    f"/api/workers/{self._worker_id}/identity",
                    headers={"Authorization": f"Bearer {self._worker_token}"},
                )
                if response.status_code in (401, 403):
                    self._identity_token = None
                    self._identity_expires_at = 0
                    raise ControlPlaneProtocolError(
                        f"Bootstrap authentication rejected: {response.status_code}"
                    )
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise ValueError("Invalid JSON response") from exc

                if not isinstance(data, dict):
                    raise ValueError("Response must be a JSON object")

                identity_token = data.get("identity_token")
                expires_at = data.get("expires_at")

                if not isinstance(identity_token, str) or not identity_token.strip():
                    raise ValueError("identity_token must be a non-empty string")
                if type(expires_at) is not int:
                    raise ValueError("expires_at must be an integer")

                if expires_at <= now + 60:
                    raise ValueError("expires_at must be safely beyond immediate refresh window")
                if expires_at > now + 3900:
                    raise ValueError("expires_at excessively distant")

                self._identity_token = identity_token
                self._identity_expires_at = expires_at
                return self._identity_token
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500:
                    raise ControlPlaneUnavailable("Control plane server error") from exc
                raise ControlPlaneProtocolError("Control plane protocol error") from exc
            except httpx.RequestError as exc:
                raise ControlPlaneUnavailable(
                    f"Transport failure: {exc.__class__.__name__}"
                ) from exc
            except (ValueError, KeyError, TypeError) as exc:
                self._identity_token = None
                self._identity_expires_at = 0
                raise ControlPlaneProtocolError(
                    "Invalid identity response from control plane"
                ) from exc

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

    async def get_latest_checkpoint(self, task_id: str) -> TaskCheckpoint | None:
        try:
            response = await self._request("GET", f"/api/tasks/{task_id}/checkpoints/latest")
            return cast(TaskCheckpoint, TaskCheckpoint.model_validate(response))
        except ControlPlaneProtocolError as e:
            if "404" in str(e):
                return None
            raise

    async def append_checkpoint(
        self, request: AppendCheckpointRequest, lease_token: str
    ) -> TaskCheckpoint:
        payload = request.model_dump(mode="json")
        payload["raw_lease_token"] = lease_token
        response = await self._request(
            "POST", f"/api/tasks/{request.checkpoint.task_id}/checkpoints", payload
        )
        return cast(TaskCheckpoint, TaskCheckpoint.model_validate(response))

    async def get_resume_decision(
        self, request: ResumeDecisionRequest, lease_token: str
    ) -> ResumeDecisionResponse:
        payload = request.model_dump(mode="json")
        response = await self._request(
            "POST", f"/api/tasks/{request.task_id}/resume-decision", payload
        )
        return cast(ResumeDecisionResponse, ResumeDecisionResponse.model_validate(response))

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None, is_retry: bool = False
    ) -> dict[str, Any]:
        identity = await self._ensure_identity()
        headers = {"X-Alpha-Worker-Identity": identity}

        try:
            kwargs = {"json": payload} if payload is not None else {}
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ControlPlaneUnavailable(
                f"Control plane unavailable: {exc.__class__.__name__}"
            ) from exc

        if response.status_code == 401 and not is_retry:
            # Token might be expired or invalidated, force refresh and retry once
            await self._ensure_identity(force_refresh=True)
            return await self._request(method, path, payload, is_retry=True)

        if response.status_code >= 500:
            raise ControlPlaneUnavailable(f"Control plane server error: {response.status_code}")
        if response.status_code >= 400:
            raise ControlPlaneProtocolError(
                f"Control plane rejected request: {response.status_code} {response.text}"
            )
        try:
            parsed = response.json()
        except ValueError as exc:
            raise ControlPlaneProtocolError("Control plane returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ControlPlaneProtocolError("Control plane response must be object")
        return parsed
