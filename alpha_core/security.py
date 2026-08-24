import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from alpha_core.config import settings


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    role: str


def _require_bearer_token(
    authorization: str | None,
    expected_token: str,
    subject: str,
    role: str,
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


def require_api_principal(
    authorization: str | None = Header(default=None),
) -> AuthPrincipal:
    return _require_bearer_token(
        authorization,
        settings.ALPHA_API_TOKEN,
        subject="alpha_api_user",
        role="admin",
    )


def require_worker_principal(
    authorization: str | None = Header(default=None),
) -> AuthPrincipal:
    return _require_bearer_token(
        authorization,
        settings.ALPHA_WORKER_TOKEN,
        subject="alpha_worker",
        role="worker",
    )


def verify_websocket_bearer(supplied_token: str | None, expected_token: str) -> bool:
    return bool(
        supplied_token
        and expected_token
        and hmac.compare_digest(supplied_token, expected_token)
    )


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
    expected_signature = base64.urlsafe_b64encode(
        hmac.new(
            settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii").rstrip("=")
    return hmac.compare_digest(supplied_signature, expected_signature)


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
    encoded_claims = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii").rstrip("=")
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
    expected_signature = base64.urlsafe_b64encode(
        hmac.new(
            settings.ALPHA_SIGNING_SECRET.encode("utf-8"),
            encoded_claims.encode("ascii"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii").rstrip("=")
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
