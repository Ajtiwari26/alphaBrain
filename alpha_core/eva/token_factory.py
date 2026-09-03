"""
alpha_core/eva/token_factory.py
LiveKit access token generator enforcing the strict read-only consumer invariant for Eva.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 4.2.1)
"""

from datetime import timedelta
from typing import Any

import jwt
from livekit.api import AccessToken, VideoGrants

from alpha_core.config import settings


class EvaSecurityInvariantError(ValueError):
    """Raised when an attempt is made to grant write or publish permissions to Eva."""


def mint_eva_consumer_token(
    room_name: str,
    identity: str = "eva-observer",
    name: str = "Eva (CTO Observer)",
    valid_minutes: int = 60,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> str:
    """Mints a cryptographically signed LiveKit token locked to read-only consumer grants.

    Invariants enforced:
    - can_publish is strictly False (Eva cannot publish media tracks)
    - can_subscribe is strictly True (Eva can ingest participant audio)
    - can_publish_data is strictly False (Eva cannot send raw data packets)
    - hidden is strictly True (Eva does not appear in human attendee roster)
    """
    if not room_name or not room_name.strip():
        raise ValueError("room_name must be non-empty")

    key = api_key or settings.LIVEKIT_API_KEY
    secret = api_secret or settings.LIVEKIT_API_SECRET
    if not key or not secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be configured")

    grants = VideoGrants(
        room_join=True,
        room=room_name.strip(),
        can_publish=False,
        can_subscribe=True,
        can_publish_data=False,
        hidden=True,
    )

    # Architectural invariant guard
    if grants.can_publish or grants.can_publish_data:
        raise EvaSecurityInvariantError(
            "Security violation: Eva consumer token cannot have publish permissions."
        )
    if not grants.hidden:
        raise EvaSecurityInvariantError(
            "Security violation: Eva consumer token must have hidden=True."
        )

    token = (
        AccessToken(key, secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_ttl(timedelta(minutes=valid_minutes))
    )
    return str(token.to_jwt())


def inspect_eva_token(token_jwt: str, api_secret: str | None = None) -> dict[str, Any]:
    """Decodes and validates that a LiveKit token adheres to Eva's read-only invariants."""
    secret = api_secret or settings.LIVEKIT_API_SECRET
    # Decode without verification if secret is not available, but verify if provided
    options = {"verify_signature": bool(secret)}
    decoded: dict[str, Any] = jwt.decode(
        token_jwt,
        key=secret or "",
        algorithms=["HS256"],
        options=options,
    )
    video = decoded.get("video", {})

    is_compliant = (
        video.get("canPublish") is False
        and video.get("canPublishData") is False
        and video.get("canSubscribe") is True
        and video.get("hidden") is True
    )

    return {
        "identity": decoded.get("sub"),
        "name": decoded.get("name"),
        "room": video.get("room"),
        "can_publish": video.get("canPublish", False),
        "can_subscribe": video.get("canSubscribe", False),
        "can_publish_data": video.get("canPublishData", False),
        "hidden": video.get("hidden", False),
        "expires_at": decoded.get("exp"),
        "is_compliant": is_compliant,
    }
