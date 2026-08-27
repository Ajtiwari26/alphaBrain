"""
Alpha Brain Security Module
===========================
Role-based access control (RBAC), bearer token authentication,
scoped stream tokens, meeting invite signing, Plivo V3 webhook
verification, nonce replay protection, secret redaction, and
project-scoped authorization guards.
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import Header, HTTPException, status

from alpha_core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------


class PrincipalRole(str, Enum):
    """All recognized roles in the Alpha Brain system."""

    FOUNDER = "founder"  # Full access: project, task, spec, deployment, worker mgmt
    ADMIN = "admin"  # System-level: equivalent to founder for API operations
    CLIENT = "client"  # Scoped: view project status, review specs, attend meetings
    WORKER = "worker"  # Task execution: lease, heartbeat, submit results
    SERVICE = "service"  # Internal: inter-service calls (e.g. AgentLine -> Alpha Brain)


# Legal permission matrix: what each role is authorized to do
ROLE_PERMISSIONS: dict[PrincipalRole, frozenset[str]] = {
    PrincipalRole.FOUNDER: frozenset(
        {
            "project:read",
            "project:write",
            "project:delete",
            "task:read",
            "task:write",
            "task:cancel",
            "spec:read",
            "spec:write",
            "spec:approve",
            "meeting:create",
            "meeting:join",
            "meeting:invite",
            "worker:read",
            "worker:manage",
            "worker:kill",
            "deployment:read",
            "deployment:approve",
            "deployment:rollback",
            "call:read",
            "call:initiate",
            "audit:read",
        }
    ),
    PrincipalRole.ADMIN: frozenset(
        {
            "project:read",
            "project:write",
            "project:delete",
            "task:read",
            "task:write",
            "task:cancel",
            "spec:read",
            "spec:write",
            "spec:approve",
            "meeting:create",
            "meeting:join",
            "meeting:invite",
            "worker:read",
            "worker:manage",
            "worker:kill",
            "deployment:read",
            "deployment:approve",
            "deployment:rollback",
            "call:read",
            "call:initiate",
            "audit:read",
        }
    ),
    PrincipalRole.CLIENT: frozenset(
        {
            "project:read",
            "spec:read",
            "spec:approve",
            "meeting:join",
            "audit:read",
        }
    ),
    PrincipalRole.WORKER: frozenset(
        {
            "task:read",
            "task:write",
            "worker:read",
        }
    ),
    PrincipalRole.SERVICE: frozenset(
        {
            "project:read",
            "task:read",
            "task:write",
            "spec:read",
            "call:read",
            "call:initiate",
            "audit:read",
        }
    ),
}


# ---------------------------------------------------------------------------
# Auth principal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthPrincipal:
    """Authenticated identity with a typed role."""

    subject: str
    role: PrincipalRole
    project_ids: tuple[str, ...] = ()

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, frozenset())

    def can_access_project(self, project_id: str) -> bool:
        """Check if principal has access to a specific project."""
        if self.role in (PrincipalRole.FOUNDER, PrincipalRole.ADMIN, PrincipalRole.SERVICE):
            return True  # Full access roles
        if not self.project_ids:
            return False  # Scoped roles fail closed when no project scope was issued
        return project_id in self.project_ids


def require_permission(principal: AuthPrincipal, permission: str) -> None:
    """Raise 403 if the principal lacks the required permission."""
    if not principal.has_permission(permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{principal.role.value}' lacks permission '{permission}'",
        )


def require_project_access(principal: AuthPrincipal, project_id: str) -> None:
    """Raise 403 if the principal cannot access the specified project."""
    if not principal.can_access_project(project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: project not in authorized scope",
        )


# ---------------------------------------------------------------------------
# Bearer token authentication
# ---------------------------------------------------------------------------


def _require_bearer_token(
    authorization: str | None,
    expected_token: str,
    subject: str,
    role: PrincipalRole,
) -> AuthPrincipal:
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    scheme, separator, supplied_token = (authorization or "").partition(" ")
    valid = (
        separator == " "
        and scheme.lower() == "bearer"
        and bool(supplied_token)
        and hmac.compare_digest(supplied_token, expected_token)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthPrincipal(subject=subject, role=role)


def create_scoped_principal_token(
    subject: str,
    role: PrincipalRole,
    project_ids: list[str] | tuple[str, ...],
    ttl_seconds: int = 3600,
) -> str:
    """Create signed HMAC token for scoped client or service principal."""
    if not settings.ALPHA_SIGNING_SECRET:
        raise RuntimeError("ALPHA_SIGNING_SECRET is not configured")
    claims = {
        "exp": int(time.time()) + ttl_seconds,
        "sub": subject,
        "role": role.value if isinstance(role, PrincipalRole) else str(role),
        "projects": list(project_ids),
    }
    encoded_claims = (
        base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    signature = hmac.new(
        settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
        encoded_claims.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded_claims}.{encoded_signature}"


def verify_scoped_principal_token(token: str | None) -> AuthPrincipal | None:
    """Validate scoped principal token and return AuthPrincipal with project scope."""
    if not token or not settings.ALPHA_SIGNING_SECRET:
        return None
    encoded_claims, separator, supplied_signature = token.partition(".")
    if separator != "." or not encoded_claims or not supplied_signature:
        return None
    expected_signature = (
        base64.urlsafe_b64encode(
            hmac.new(
                settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
                encoded_claims.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    try:
        padded = encoded_claims + "=" * (-len(encoded_claims) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    if not isinstance(claims.get("exp"), int) or claims["exp"] < int(time.time()):
        return None
    role_str = claims.get("role")
    try:
        role = PrincipalRole(role_str)
    except ValueError:
        return None
    subject = str(claims.get("sub", "anonymous"))
    project_ids = tuple(claims.get("projects", []))
    return AuthPrincipal(subject=subject, role=role, project_ids=project_ids)


def require_api_principal(
    authorization: str | None = Header(default=None),
) -> AuthPrincipal:
    """FastAPI dependency: authenticate founder/admin API requests or scoped client tokens."""
    if not settings.ALPHA_API_TOKEN and not settings.ALPHA_SIGNING_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    scheme, separator, supplied_token = (authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not supplied_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 1. Match full founder/admin token
    if settings.ALPHA_API_TOKEN and hmac.compare_digest(supplied_token, settings.ALPHA_API_TOKEN):
        return AuthPrincipal(subject="alpha_api_user", role=PrincipalRole.FOUNDER)
    # 2. Check signed scoped token (e.g. client token with project_ids)
    scoped = verify_scoped_principal_token(supplied_token)
    if scoped:
        return scoped
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_worker_principal(
    authorization: str | None = Header(default=None),
    x_alpha_worker_identity: str | None = Header(default=None),
) -> AuthPrincipal:
    """FastAPI dependency: authenticate worker daemon requests."""
    shared_principal = _require_bearer_token(
        authorization,
        settings.ALPHA_WORKER_TOKEN,
        subject="alpha_worker",
        role=PrincipalRole.WORKER,
    )
    if not x_alpha_worker_identity:
        return shared_principal
    claims = verify_worker_identity_token(x_alpha_worker_identity)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker identity"
        )
    return AuthPrincipal(subject=str(claims["sub"]), role=PrincipalRole.WORKER)


def verify_websocket_bearer(supplied_token: str | None, expected_token: str) -> bool:
    return bool(
        supplied_token and expected_token and hmac.compare_digest(supplied_token, expected_token)
    )


# ---------------------------------------------------------------------------
# Scoped stream tokens (short-lived HMAC)
# ---------------------------------------------------------------------------


def create_scoped_stream_token(scope: str, ttl_seconds: int = 300) -> str:
    if not settings.ALPHA_SIGNING_SECRET:
        raise RuntimeError("ALPHA_SIGNING_SECRET is not configured")
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{scope}:{expires_at}"
    signature = hmac.new(
        settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{expires_at}.{encoded_signature}"


def verify_scoped_stream_token(token: str | None, scope: str) -> bool:
    if not token or not settings.ALPHA_SIGNING_SECRET:
        return False
    expires_text, separator, supplied_signature = token.partition(".")
    if separator != "." or not expires_text.isdigit() or not supplied_signature:
        return False
    expires_at = int(expires_text)
    if expires_at < int(time.time()):
        return False
    payload = f"{scope}:{expires_at}"
    expected_signature = (
        base64.urlsafe_b64encode(
            hmac.new(
                settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    return hmac.compare_digest(supplied_signature, expected_signature)


# ---------------------------------------------------------------------------
# Worker identity tokens (short-lived signed worker credentials)
# ---------------------------------------------------------------------------


def create_worker_identity_token(
    worker_id: str,
    capabilities: list[str] | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Create a signed short-lived token for worker authentication."""
    if not settings.ALPHA_SIGNING_SECRET:
        raise RuntimeError("ALPHA_SIGNING_SECRET is not configured")
    claims = {
        "exp": int(time.time()) + ttl_seconds,
        "sub": worker_id,
        "role": PrincipalRole.WORKER.value,
        "cap": capabilities or [],
    }
    encoded_claims = (
        base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    signature = hmac.new(
        settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
        encoded_claims.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded_claims}.{encoded_signature}"


def verify_worker_identity_token(token: str | None) -> dict[str, Any] | None:
    """Validate worker identity token and return trusted claims."""
    if not token or not settings.ALPHA_SIGNING_SECRET:
        return None
    encoded_claims, separator, supplied_signature = token.partition(".")
    if separator != "." or not encoded_claims or not supplied_signature:
        return None
    expected_signature = (
        base64.urlsafe_b64encode(
            hmac.new(
                settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
                encoded_claims.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    try:
        padded = encoded_claims + "=" * (-len(encoded_claims) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    if not isinstance(claims.get("exp"), int) or claims["exp"] < int(time.time()):
        return None
    if claims.get("role") != PrincipalRole.WORKER.value:
        return None
    return claims


# ---------------------------------------------------------------------------
# Meeting invite tokens
# ---------------------------------------------------------------------------


def create_meeting_invite(
    room_name: str,
    identity: str,
    role: str = "client",
    ttl_seconds: int = 3600,
) -> str:
    """Create signed, short-lived claims for one meeting participant."""
    if not settings.ALPHA_SIGNING_SECRET:
        raise RuntimeError("ALPHA_SIGNING_SECRET is not configured")
    claims = {
        "exp": int(time.time()) + ttl_seconds,
        "identity": identity,
        "role": role,
        "room": room_name,
    }
    encoded_claims = (
        base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    signature = hmac.new(
        settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
        encoded_claims.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded_claims}.{encoded_signature}"


def verify_meeting_invite(token: str | None) -> dict[str, object] | None:
    """Validate meeting invite integrity and expiry, returning trusted claims."""
    if not token or not settings.ALPHA_SIGNING_SECRET:
        return None
    encoded_claims, separator, supplied_signature = token.partition(".")
    if separator != "." or not encoded_claims or not supplied_signature:
        return None
    expected_signature = (
        base64.urlsafe_b64encode(
            hmac.new(
                settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
                encoded_claims.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    try:
        padded = encoded_claims + "=" * (-len(encoded_claims) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    expires_at = claims.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return None
    if not all(isinstance(claims.get(key), str) for key in ("identity", "role", "room")):
        return None
    return claims


# ---------------------------------------------------------------------------
# Plivo V3 webhook signature verification
# ---------------------------------------------------------------------------


def validate_plivo_v3_signature(
    method: str,
    uri: str,
    nonce: str,
    auth_token: str,
    supplied_signatures: str,
    params: Mapping[str, str] | None = None,
) -> bool:
    if not nonce or not auth_token or not supplied_signatures:
        return False

    assembled = uri
    if method.upper() == "POST" and params:
        for key in sorted(params):
            assembled += f"{key}{params[key]}"
    assembled += nonce

    expected = base64.b64encode(
        hmac.new(
            auth_token.encode("utf-8"),
            assembled.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    return any(
        hmac.compare_digest(candidate.strip(), expected)
        for candidate in supplied_signatures.split(",")
        if candidate.strip()
    )


class NonceReplayCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}

    def consume(self, nonce: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.ttl_seconds
        self._seen = {key: seen_at for key, seen_at in self._seen.items() if seen_at >= cutoff}
        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True


plivo_nonce_cache = NonceReplayCache()


# ---------------------------------------------------------------------------
# Secret redaction filter
# ---------------------------------------------------------------------------

# Patterns that look like secrets: API keys, tokens, passwords, signing secrets
_SECRET_PATTERNS = [
    re.compile(r"(AIza[A-Za-z0-9_-]{35})", re.ASCII),  # Google API key
    re.compile(r"(sk-[A-Za-z0-9]{20,})", re.ASCII),  # OpenAI/generic
    re.compile(r"(AQ\.[A-Za-z0-9_-]{10,})", re.ASCII),  # Stitch API key
    re.compile(r"(ghp_[A-Za-z0-9]{36,})", re.ASCII),  # GitHub PAT
    re.compile(r"(Bearer\s+[A-Za-z0-9._-]{20,})", re.ASCII),  # Bearer tokens
    re.compile(r"(-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----)", re.ASCII),  # Private keys
]

_KV_SECRET_PATTERN = re.compile(
    r"(?i)\b([A-Za-z0-9_-]*(?:token|secret|api[_-]?key|password|auth|access|signing)[A-Za-z0-9_-]*)(\s*[=:]\s*)([^\s,;\"'}{]+)",
    re.ASCII,
)

# Known setting names that should always be redacted
_SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "api_secret",
        "auth_token",
        "password",
        "secret",
        "signing_secret",
        "access_token",
        "bearer_token",
        "private_key",
        "livekit_api_secret",
        "alpha_api_token",
        "alpha_worker_token",
        "alpha_signing_secret",
        "gemini_api_key",
        "plivo_auth_token",
    }
)

REDACTED = "[REDACTED]"


def redact_secrets(text: str) -> str:
    """Scrub known secret patterns from a string for safe logging."""
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(REDACTED, result)
    result = _KV_SECRET_PATTERN.sub(r"\1\2" + REDACTED, result)
    return result


def redact_dict(data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Recursively redact secret-looking keys in a dictionary."""
    if depth > 10:
        return data
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower().replace("-", "_")
        if key_lower in _SECRET_FIELD_NAMES or "secret" in key_lower or "password" in key_lower:
            cleaned[key] = REDACTED
        elif isinstance(value, dict):
            cleaned[key] = redact_dict(value, depth + 1)
        elif isinstance(value, str):
            cleaned[key] = redact_secrets(value)
        elif isinstance(value, list):
            cleaned[key] = [
                redact_dict(item, depth + 1)
                if isinstance(item, dict)
                else redact_secrets(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


# ---------------------------------------------------------------------------
# Worker kill switch
# ---------------------------------------------------------------------------


class WorkerKillSwitch:
    """Global and per-project worker pause/kill mechanism."""

    def __init__(self) -> None:
        self._global_killed = False
        self._paused_projects: set[str] = set()

    @property
    def is_globally_killed(self) -> bool:
        return self._global_killed

    def kill_all(self) -> None:
        """Emergency stop: prevent all worker task execution."""
        self._global_killed = True
        logger.warning("KILL SWITCH ACTIVATED: all worker execution halted")

    def resume_all(self) -> None:
        """Resume global worker execution."""
        self._global_killed = False
        self._paused_projects.clear()
        logger.info("Kill switch deactivated: worker execution resumed")

    def pause_project(self, project_id: str) -> None:
        """Pause task execution for a specific project."""
        self._paused_projects.add(project_id)
        logger.info("Project %s paused", project_id)

    def resume_project(self, project_id: str) -> None:
        """Resume task execution for a specific project."""
        self._paused_projects.discard(project_id)
        logger.info("Project %s resumed", project_id)

    def can_execute(self, project_id: str | None = None) -> bool:
        """Check if execution is allowed globally and for the given project."""
        if self._global_killed:
            return False
        if project_id and project_id in self._paused_projects:
            return False
        return True


# Singleton instance
worker_kill_switch = WorkerKillSwitch()


# ---------------------------------------------------------------------------
# Artifact path validation
# ---------------------------------------------------------------------------

_SAFE_ARTIFACT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")


def validate_artifact_identifier(artifact_id: str) -> bool:
    """Reject unsafe artifact identifiers (path traversal, special chars)."""
    if not artifact_id or not _SAFE_ARTIFACT_PATTERN.match(artifact_id):
        return False
    if ".." in artifact_id or artifact_id.startswith("/"):
        return False
    return True


def require_safe_artifact_id(artifact_id: str) -> str:
    """Raise 400 if artifact ID contains unsafe characters or traversal."""
    if not validate_artifact_identifier(artifact_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsafe artifact identifier: {artifact_id!r}",
        )
    return artifact_id
