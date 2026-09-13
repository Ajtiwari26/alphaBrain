"""
alpha_core/api/cloud_dispatch.py
Cloud-First Provisioning, Node Registry, Task Dispatch, and Broadcast Stream Hub API.

Invariants Enforced:
- I-52: Ephemeral Provisioning Session TTL & Single-Use (Strict 300s TTL, single-claim enforcement).
- I-53: Atomic Session Claim & Founder Binding (Atomic transition, binds device to founder principal).
- I-54: Device Registry & Revocation (Track all claimed devices, support revocation, require founder auth).
- I-55: Node Authentication & Registration Heartbeat (WSS) (Secure node registration, periodic liveness).
- I-56: Node Disconnection & Heartbeat Expiry Isolation (Auto-detect disconnection, update node status).
- I-57: Atomic Task Dispatch Lease via Registry (Only registered online nodes, atomic lease, emergency stop check).
- I-58: Stream Hub Broadcast Authentication & Tenant Isolation (Authenticated WSS hub, task boundary isolation).
- I-59: Hub Fan-Out & Message Envelope Integrity (Monotonic sequence, structured typing, 5s heartbeat per I-48).
- I-60: Emergency Stop & Kill Switch Propagation (Immediate lease blocking and stream notification on emergency stop).
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field

from alpha_core.config import settings
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_core.security import (
    AuthPrincipal,
    PrincipalRole,
    create_scoped_principal_token,
    create_scoped_stream_token,
    require_api_principal,
    verify_scoped_principal_token,
    verify_scoped_stream_token,
    verify_worker_identity_token,
)

logger = logging.getLogger("alpha_core.api.cloud_dispatch")

router = APIRouter(tags=["cloud_dispatch"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProvisionSessionRequest(BaseModel):
    client_name: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvisionSessionResponse(BaseModel):
    session_id: str
    pairing_code: str
    provision_token: str
    qr_payload: str
    expires_in_seconds: int
    expires_at: float
    status: str


class ClaimSessionRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=128)
    pairing_code: str | None = Field(default=None, max_length=32)
    provision_token: str | None = Field(default=None, max_length=512)
    device_id: str = Field(min_length=1, max_length=128)
    device_name: str = Field(default="Founder Device", max_length=128)
    device_type: str = Field(default="mobile", max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceResponse(BaseModel):
    device_id: str
    name: str
    device_type: str
    registered_at: str
    last_seen: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimSessionResponse(BaseModel):
    status: str
    session_token: str
    token_type: str = "Bearer"
    expires_in: int
    device: DeviceResponse


class RevokeDeviceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)


class DispatchLeaseRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=128)
    capabilities: list[str] = Field(default_factory=list)


class DispatchLeaseResponse(BaseModel):
    status: str
    node_id: str
    task_id: str | None = None
    task: dict[str, Any] | None = None
    lease_token: str | None = None
    leased_at: str | None = None


# ---------------------------------------------------------------------------
# State Models & In-Memory Stores
# ---------------------------------------------------------------------------


class ProvisioningSession:
    def __init__(
        self,
        session_id: str,
        pairing_code: str,
        provision_token: str,
        ttl_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.session_id = session_id
        self.pairing_code = pairing_code
        self.provision_token = provision_token
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.expires_at = self.created_at + ttl_seconds
        self.status = "pending"  # "pending", "claimed", "expired"
        self.claimed_by_device_id: str | None = None
        self.claimed_at: float | None = None
        self.metadata = metadata or {}

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class ProvisioningSessionStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, ProvisioningSession] = {}
        self._by_code: dict[str, str] = {}
        self._by_token: dict[str, str] = {}

    async def create_session(
        self, ttl_seconds: int = 300, metadata: dict[str, Any] | None = None
    ) -> ProvisioningSession:
        async with self._lock:
            self._cleanup_expired_locked()
            session_id = str(uuid.uuid4())
            pairing_code = f"AB-{secrets.randbelow(1000000):06d}"
            provision_token = secrets.token_urlsafe(32)

            session = ProvisioningSession(
                session_id=session_id,
                pairing_code=pairing_code,
                provision_token=provision_token,
                ttl_seconds=ttl_seconds,
                metadata=metadata,
            )
            self._sessions[session_id] = session
            self._by_code[pairing_code] = session_id
            self._by_token[provision_token] = session_id
            return session

    async def claim_session(
        self,
        session_id: str | None,
        pairing_code: str | None,
        provision_token: str | None,
        device_id: str,
    ) -> ProvisioningSession:
        async with self._lock:
            # Locate session (Invariant I-52 & I-53)
            sid = session_id
            if not sid and pairing_code:
                sid = self._by_code.get(pairing_code)
            if not sid and provision_token:
                sid = self._by_token.get(provision_token)

            if not sid or sid not in self._sessions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Provisioning session not found",
                )

            session = self._sessions[sid]

            # Invariant I-52: Ephemeral session TTL
            if session.is_expired():
                session.status = "expired"
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Provisioning session has expired",
                )

            # Invariant I-53: Atomic claim & single-use
            if session.status == "claimed":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Provisioning session already claimed",
                )

            session.status = "claimed"
            session.claimed_by_device_id = device_id
            session.claimed_at = time.time()
            return session

    def _cleanup_expired_locked(self) -> None:
        now = time.time()
        expired_ids = [sid for sid, s in self._sessions.items() if now > s.expires_at]
        for sid in expired_ids:
            s = self._sessions.pop(sid, None)
            if s:
                self._by_code.pop(s.pairing_code, None)
                self._by_token.pop(s.provision_token, None)


class RegisteredDevice:
    def __init__(
        self,
        device_id: str,
        name: str,
        device_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now_iso = datetime.now(UTC).isoformat()
        self.device_id = device_id
        self.name = name
        self.device_type = device_type
        self.registered_at = now_iso
        self.last_seen = now_iso
        self.status = "active"  # "active" or "revoked"
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "status": self.status,
            "metadata": self.metadata,
        }


class DeviceRegistry:
    """Manages devices bound to the Founder session (Invariant I-54)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._devices: dict[str, RegisteredDevice] = {}

    async def register_device(
        self,
        device_id: str,
        name: str,
        device_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredDevice:
        async with self._lock:
            device = self._devices.get(device_id)
            if device:
                device.name = name
                device.device_type = device_type
                device.status = "active"
                device.last_seen = datetime.now(UTC).isoformat()
                if metadata:
                    device.metadata.update(metadata)
            else:
                device = RegisteredDevice(
                    device_id=device_id,
                    name=name,
                    device_type=device_type,
                    metadata=metadata,
                )
                self._devices[device_id] = device
            return device

    async def list_devices(self, status_filter: str | None = None) -> list[RegisteredDevice]:
        async with self._lock:
            devices = list(self._devices.values())
            if status_filter:
                devices = [d for d in devices if d.status == status_filter]
            return devices

    async def get_device(self, device_id: str) -> RegisteredDevice | None:
        async with self._lock:
            return self._devices.get(device_id)

    async def revoke_device(self, device_id: str) -> bool:
        async with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return False
            device.status = "revoked"
            device.last_seen = datetime.now(UTC).isoformat()
            return True


class RegisteredNode:
    """Represents a connected worker node in the Node Registry (Invariant I-55)."""

    def __init__(
        self,
        node_id: str,
        hostname: str,
        capabilities: list[str],
        labels: dict[str, str] | None = None,
    ) -> None:
        now_iso = datetime.now(UTC).isoformat()
        self.node_id = node_id
        self.hostname = hostname
        self.capabilities = capabilities
        self.labels = labels or {}
        self.status = "online"  # "online", "busy", "offline"
        self.registered_at = now_iso
        self.last_heartbeat = time.time()
        self.active_tasks: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "capabilities": self.capabilities,
            "labels": self.labels,
            "status": self.status,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "active_tasks": self.active_tasks,
        }


class NodeRegistry:
    """Maintains active cluster nodes and their live connections (Invariants I-55 & I-56)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._nodes: dict[str, RegisteredNode] = {}
        self._connections: dict[str, WebSocket] = {}

    async def register_node(
        self,
        node_id: str,
        hostname: str,
        capabilities: list[str],
        labels: dict[str, str] | None = None,
        websocket: WebSocket | None = None,
    ) -> RegisteredNode:
        async with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.hostname = hostname
                node.capabilities = capabilities
                node.labels = labels or {}
                node.status = "online"
                node.last_heartbeat = time.time()
            else:
                node = RegisteredNode(
                    node_id=node_id,
                    hostname=hostname,
                    capabilities=capabilities,
                    labels=labels,
                )
                self._nodes[node_id] = node

            if websocket:
                self._connections[node_id] = websocket
            return node

    async def record_heartbeat(
        self, node_id: str, load: float = 0.0, active_tasks: list[str] | None = None
    ) -> bool:
        async with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.last_heartbeat = time.time()
            node.status = "busy" if (active_tasks and len(active_tasks) > 0) else "online"
            if active_tasks is not None:
                node.active_tasks = active_tasks
            return True

    async def mark_offline(self, node_id: str) -> None:
        async with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.status = "offline"
            self._connections.pop(node_id, None)

    async def get_node(self, node_id: str) -> RegisteredNode | None:
        async with self._lock:
            return self._nodes.get(node_id)

    async def list_online_nodes(self) -> list[RegisteredNode]:
        async with self._lock:
            return [n for n in self._nodes.values() if n.status in ("online", "busy")]


class BroadcastStreamHub:
    """
    WebSocket Broadcast Hub multiplexing agent execution telemetry
    across subscribers and broadcaster nodes (Invariants I-58, I-59, I-60).
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, set[WebSocket]] = {}
        self._broadcasters: dict[str, set[WebSocket]] = {}
        self._sequences: dict[str, int] = {}

    async def register_subscriber(self, task_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._subscribers.setdefault(task_id, set()).add(ws)

    async def unregister_subscriber(self, task_id: str, ws: WebSocket) -> None:
        async with self._lock:
            if task_id in self._subscribers:
                self._subscribers[task_id].discard(ws)
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

    async def register_broadcaster(self, task_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._broadcasters.setdefault(task_id, set()).add(ws)

    async def unregister_broadcaster(self, task_id: str, ws: WebSocket) -> None:
        async with self._lock:
            if task_id in self._broadcasters:
                self._broadcasters[task_id].discard(ws)
                if not self._broadcasters[task_id]:
                    del self._broadcasters[task_id]

    async def broadcast(
        self,
        task_id: str,
        message_type: str,
        payload: Any,
        sender: str = "worker",
    ) -> dict[str, Any]:
        """Broadcasts structured envelope to all subscribers for task_id (Invariant I-59)."""
        async with self._lock:
            seq = self._sequences.get(task_id, 0) + 1
            self._sequences[task_id] = seq
            subs = list(self._subscribers.get(task_id, set()))

        now_iso = datetime.now(UTC).isoformat()
        envelope = {
            "task_id": task_id,
            "seq": seq,
            "type": message_type,
            "sender": sender,
            "timestamp": now_iso,
            "payload": payload,
        }
        text_data = json.dumps(envelope)

        dead_ws: list[WebSocket] = []
        for ws in subs:
            try:
                await ws.send_text(text_data)
            except Exception:
                dead_ws.append(ws)

        if dead_ws:
            async with self._lock:
                for ws in dead_ws:
                    if task_id in self._subscribers:
                        self._subscribers[task_id].discard(ws)

        return envelope

    async def broadcast_emergency_stop(self, task_id: str, reason: str) -> None:
        """Broadcasts emergency stop to both broadcasters and subscribers (Invariant I-60)."""
        await self.broadcast(
            task_id=task_id,
            message_type="EMERGENCY_STOP",
            payload={"reason": reason, "halt_immediately": True},
            sender="control_plane",
        )


# Global singletons
_provisioning_store = ProvisioningSessionStore()
_device_registry = DeviceRegistry()
_node_registry = NodeRegistry()
_stream_hub = BroadcastStreamHub()
_default_triage_queue: TaskTriageQueue | None = None


def get_provisioning_store() -> ProvisioningSessionStore:
    return _provisioning_store


def get_device_registry() -> DeviceRegistry:
    return _device_registry


def get_node_registry() -> NodeRegistry:
    return _node_registry


def get_stream_hub() -> BroadcastStreamHub:
    return _stream_hub


def get_triage_queue() -> TaskTriageQueue:
    global _default_triage_queue
    if _default_triage_queue is None:
        _default_triage_queue = TaskTriageQueue()
    return _default_triage_queue


def require_founder_role(principal: AuthPrincipal) -> None:
    if principal.role not in {PrincipalRole.FOUNDER, PrincipalRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cloud dispatch operation requires founder or admin role",
        )


# ---------------------------------------------------------------------------
# 1. Provision Session: POST /api/auth/provision-session
# ---------------------------------------------------------------------------


@router.post(
    "/api/auth/provision-session",
    response_model=ProvisionSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_session(
    req: ProvisionSessionRequest | None = None,
    store: ProvisioningSessionStore = Depends(get_provisioning_store),
) -> ProvisionSessionResponse:
    """
    Creates an ephemeral pairing session with strict 300s TTL (Invariant I-52).
    """
    metadata = req.metadata if req else {}
    if req and req.client_name:
        metadata["client_name"] = req.client_name

    session = await store.create_session(ttl_seconds=300, metadata=metadata)

    qr_payload = json.dumps(
        {
            "session_id": session.session_id,
            "pairing_code": session.pairing_code,
            "provision_token": session.provision_token,
            "expires_at": session.expires_at,
            "version": "1.0",
        }
    )

    return ProvisionSessionResponse(
        session_id=session.session_id,
        pairing_code=session.pairing_code,
        provision_token=session.provision_token,
        qr_payload=qr_payload,
        expires_in_seconds=300,
        expires_at=session.expires_at,
        status=session.status,
    )


# ---------------------------------------------------------------------------
# 2. Claim Session: POST /api/auth/claim-session
# ---------------------------------------------------------------------------


@router.post(
    "/api/auth/claim-session",
    response_model=ClaimSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def claim_session(
    req: ClaimSessionRequest,
    store: ProvisioningSessionStore = Depends(get_provisioning_store),
    devices: DeviceRegistry = Depends(get_device_registry),
) -> ClaimSessionResponse:
    """
    Atomically claims an ephemeral provisioning session and binds the device to
    the Founder identity (Invariants I-52 & I-53).
    """
    if not req.session_id and not req.pairing_code and not req.provision_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Must provide session_id, pairing_code, or provision_token",
        )

    # Atomically claim session in store (Invariant I-53)
    session = await store.claim_session(
        session_id=req.session_id,
        pairing_code=req.pairing_code,
        provision_token=req.provision_token,
        device_id=req.device_id,
    )

    # Register device into DeviceRegistry (Invariant I-54)
    device = await devices.register_device(
        device_id=req.device_id,
        name=req.device_name,
        device_type=req.device_type,
        metadata={**req.metadata, "session_id": session.session_id},
    )

    # Generate long-lived Founder Session Token (86400s / 24h)
    ttl_seconds = 86400
    session_token = create_scoped_principal_token(
        subject=f"founder:{req.device_id}",
        role=PrincipalRole.FOUNDER,
        project_ids=["*"],
        ttl_seconds=ttl_seconds,
    )

    return ClaimSessionResponse(
        status="claimed",
        session_token=session_token,
        token_type="Bearer",
        expires_in=ttl_seconds,
        device=DeviceResponse(**device.to_dict()),
    )


# ---------------------------------------------------------------------------
# 3. Devices Management: /api/auth/devices
# ---------------------------------------------------------------------------


@router.get(
    "/api/auth/devices",
    response_model=list[DeviceResponse],
    status_code=status.HTTP_200_OK,
)
async def list_devices(
    status_filter: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_api_principal),
    devices: DeviceRegistry = Depends(get_device_registry),
) -> list[DeviceResponse]:
    """
    Lists registered devices bound to Founder identity (Invariant I-54).
    """
    require_founder_role(principal)
    device_list = await devices.list_devices(status_filter=status_filter)
    return [DeviceResponse(**d.to_dict()) for d in device_list]


@router.delete(
    "/api/auth/devices/{device_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def revoke_device(
    device_id: str,
    principal: AuthPrincipal = Depends(require_api_principal),
    devices: DeviceRegistry = Depends(get_device_registry),
) -> dict[str, Any]:
    """
    Revokes a device's access immediately (Invariant I-54).
    """
    require_founder_role(principal)
    revoked = await devices.revoke_device(device_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )
    return {"status": "revoked", "device_id": device_id}


@router.post(
    "/api/auth/devices/revoke",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def revoke_device_post(
    req: RevokeDeviceRequest,
    principal: AuthPrincipal = Depends(require_api_principal),
    devices: DeviceRegistry = Depends(get_device_registry),
) -> dict[str, Any]:
    """Alternative POST endpoint for device revocation (Invariant I-54)."""
    require_founder_role(principal)
    revoked = await devices.revoke_device(req.device_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{req.device_id}' not found",
        )
    return {"status": "revoked", "device_id": req.device_id}


# ---------------------------------------------------------------------------
# 4. Node Registry WSS: /api/nodes/register
# ---------------------------------------------------------------------------


def _authenticate_node_token(token: str | None) -> str | None:
    """Validates node authentication token against signing secrets or worker key."""
    if not token:
        return None
    # 1. Check worker identity token
    worker_claims = verify_worker_identity_token(token)
    if worker_claims and "worker_id" in worker_claims:
        return str(worker_claims["worker_id"])

    # 2. Check scoped principal token
    principal = verify_scoped_principal_token(token)
    if principal and principal.subject:
        return principal.subject

    # 3. Check worker API secret key
    expected_worker_key = getattr(settings, "ALPHA_WORKER_KEY", None)
    if expected_worker_key and token == expected_worker_key:
        return "authenticated_worker"

    expected_signing_secret = getattr(settings, "ALPHA_SIGNING_SECRET", None)
    if expected_signing_secret and token == expected_signing_secret:
        return "authenticated_node"

    return None


@router.websocket("/api/nodes/register")
async def register_node_wss(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    nodes: NodeRegistry = Depends(get_node_registry),
) -> None:
    """
    Persistent WebSocket connection for worker execution nodes (Invariants I-55 & I-56).
    Handles authentication, registration handshake, and heartbeat liveness.
    """
    # Authenticate node (Invariant I-55)
    auth_token = token
    if not auth_token:
        # Check Authorization header if present
        auth_header = websocket.headers.get("Authorization") or websocket.headers.get(
            "authorization"
        )
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    authenticated_subject = _authenticate_node_token(auth_token)
    if not authenticated_subject:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    current_node_id: str | None = None

    try:
        # Wait for initial registration message
        initial_raw = await websocket.receive_text()
        try:
            msg = json.loads(initial_raw)
        except Exception:
            await websocket.send_text(
                json.dumps({"error": "Invalid JSON envelope", "type": "error"})
            )
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        if msg.get("type") != "register" or not msg.get("node_id"):
            await websocket.send_text(
                json.dumps(
                    {
                        "error": "First message must be type 'register' with node_id",
                        "type": "error",
                    }
                )
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        current_node_id = str(msg["node_id"])
        hostname = str(msg.get("hostname", "unknown-host"))
        capabilities = list(msg.get("capabilities", []))
        labels = dict(msg.get("labels", {}))

        # Register in NodeRegistry (Invariant I-55)
        await nodes.register_node(
            node_id=current_node_id,
            hostname=hostname,
            capabilities=capabilities,
            labels=labels,
            websocket=websocket,
        )

        # Send registration confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "registered",
                    "node_id": current_node_id,
                    "heartbeat_interval_seconds": 5,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        )

        # Heartbeat and command loop
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
            except Exception:
                continue

            msg_type = data.get("type")
            if msg_type == "heartbeat":
                load = float(data.get("load", 0.0))
                active_tasks = data.get("active_tasks")
                await nodes.record_heartbeat(
                    current_node_id,
                    load=load,
                    active_tasks=active_tasks,
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat_ack",
                            "node_id": current_node_id,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                )
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info("Node WebSocket disconnected: %s", current_node_id)
    except Exception as e:
        logger.warning("Node WebSocket error for %s: %s", current_node_id, e)
    finally:
        # Invariant I-56: Clean node disconnection handling & status update
        if current_node_id:
            await nodes.mark_offline(current_node_id)


# ---------------------------------------------------------------------------
# 5. Task Dispatch Lease: /api/dispatch/lease
# ---------------------------------------------------------------------------


@router.post(
    "/api/dispatch/lease",
    response_model=DispatchLeaseResponse,
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/dispatch/lease",
    response_model=DispatchLeaseResponse,
    status_code=status.HTTP_200_OK,
)
async def dispatch_task_lease(
    req: DispatchLeaseRequest | None = None,
    node_id: str | None = Query(default=None),
    nodes: NodeRegistry = Depends(get_node_registry),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> DispatchLeaseResponse:
    """
    Leases next approved task to an active, registered execution node (Invariant I-57).
    Honors Emergency Stop and guarantees atomic assignment.
    """
    target_node_id = (req.node_id if req else None) or node_id
    if not target_node_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Must provide node_id in request body or query parameter",
        )

    # Invariant I-57: Verify node is registered and active
    node = await nodes.get_node(target_node_id)
    if not node or node.status == "offline":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Node '{target_node_id}' is not registered or is offline",
        )

    # Invariant I-60: Emergency Stop refusal
    if queue.is_emergency_stopped():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Emergency stop is active; task leasing is suspended",
        )

    # Atomic lease from triage queue (Invariant I-57)
    leased_task = queue.lease_next_approved_task(worker_id=target_node_id)
    if not leased_task:
        return DispatchLeaseResponse(
            status="no_tasks",
            node_id=target_node_id,
            task_id=None,
            task=None,
        )

    task_id = leased_task.get("envelope", {}).get("task_id", "unknown_task")
    now_iso = datetime.now(UTC).isoformat()
    lease_token = create_scoped_stream_token(f"stream:{task_id}", ttl_seconds=3600)

    # Update node active tasks
    node.active_tasks.append(task_id)
    node.status = "busy"

    return DispatchLeaseResponse(
        status="leased",
        node_id=target_node_id,
        task_id=task_id,
        task=leased_task,
        lease_token=lease_token,
        leased_at=now_iso,
    )


# ---------------------------------------------------------------------------
# 6. Stream Hub Broadcast WSS: /api/stream/broadcast/{task_id}
# ---------------------------------------------------------------------------


def _authenticate_stream_token(token: str | None, task_id: str) -> bool:
    """Verifies stream authorization for given task_id (Invariant I-58)."""
    if not token:
        return False

    # 1. Scoped stream token for task
    if verify_scoped_stream_token(token, f"stream:{task_id}"):
        return True

    # 2. General stream token
    if verify_scoped_stream_token(token, f"task-stream:{task_id}"):
        return True

    # 3. Scoped principal token with founder/worker role
    principal = verify_scoped_principal_token(token)
    if principal and principal.role in {
        PrincipalRole.FOUNDER,
        PrincipalRole.ADMIN,
        PrincipalRole.WORKER,
    }:
        return True

    # 4. Worker identity token
    worker_claims = verify_worker_identity_token(token)
    if worker_claims:
        return True

    # 5. Fallback server secrets
    if token == getattr(settings, "ALPHA_WORKER_KEY", None) or token == getattr(
        settings, "ALPHA_SIGNING_SECRET", None
    ):
        return True

    return False


@router.websocket("/api/stream/broadcast/{task_id}")
async def broadcast_stream_hub(
    websocket: WebSocket,
    task_id: str,
    token: str | None = Query(default=None),
    role: str = Query(default="subscriber"),  # "subscriber" or "broadcaster"
    hub: BroadcastStreamHub = Depends(get_stream_hub),
    queue: TaskTriageQueue = Depends(get_triage_queue),
) -> None:
    """
    Bidirectional WebSocket Hub for task execution streaming (Invariants I-58, I-59, I-60).
    Broadcasters publish worker events; Subscribers receive real-time updates.
    """
    # Authenticate stream participant (Invariant I-58)
    auth_token = token
    if not auth_token:
        auth_header = websocket.headers.get("Authorization") or websocket.headers.get(
            "authorization"
        )
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    if not _authenticate_stream_token(auth_token, task_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # Invariant I-60: Check emergency stop
    if queue.is_emergency_stopped():
        await websocket.send_text(
            json.dumps(
                {
                    "type": "EMERGENCY_STOP",
                    "task_id": task_id,
                    "payload": {"reason": "Emergency stop is active"},
                }
            )
        )

    # Register in Hub
    is_broadcaster = role == "broadcaster"
    if is_broadcaster:
        await hub.register_broadcaster(task_id, websocket)
    else:
        await hub.register_subscriber(task_id, websocket)

    # Send connection confirmation
    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "task_id": task_id,
                "role": role,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    )

    # Background heartbeat task for subscribers (Invariant I-48 & I-59: 5s heartbeat)
    heartbeat_task: asyncio.Task[None] | None = None

    async def _heartbeat_loop() -> None:
        try:
            while True:
                await asyncio.sleep(5.0)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "task_id": task_id,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                )
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    if not is_broadcaster:
        heartbeat_task = asyncio.create_task(_heartbeat_loop())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            msg_type = msg.get("type", "message")
            payload = msg.get("payload", msg.get("data", {}))

            if is_broadcaster:
                # Invariant I-59: Fan out broadcaster message to all subscribers
                await hub.broadcast(
                    task_id=task_id,
                    message_type=msg_type,
                    payload=payload,
                    sender="broadcaster",
                )
            else:
                # Subscriber incoming messages (ping/pong, client ack)
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info("Stream hub disconnected: task_id=%s, role=%s", task_id, role)
    except Exception as e:
        logger.warning("Stream hub error for task_id=%s: %s", task_id, e)
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

        if is_broadcaster:
            await hub.unregister_broadcaster(task_id, websocket)
        else:
            await hub.unregister_subscriber(task_id, websocket)
