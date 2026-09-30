from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from alpha_core.config import settings

MeetingRole = Literal["founder", "client", "eva", "translator", "transcriber"]


def _grants_for_role(role: MeetingRole) -> dict[str, bool]:
    return {
        "can_publish": True,
        "can_subscribe": True,
        "can_publish_data": True,
        "can_update_own_metadata": role in {"founder", "eva"},
        "room_admin": role == "founder",
    }


class LiveKitTokenGenerator:
    """Generates secure, signed WebRTC room access tokens for LiveKit."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.LIVEKIT_API_KEY
        self.api_secret = api_secret or settings.LIVEKIT_API_SECRET

    def generate_token(
        self,
        room_name: str,
        participant_identity: str,
        participant_name: str | None = None,
        role: MeetingRole = "client",
        valid_minutes: int = 30,
    ) -> str:
        """Generates a signed JWT token with video grants for the specified room."""
        grants = _grants_for_role(role)
        try:
            from livekit.api import AccessToken, VideoGrants

            token = (
                AccessToken(self.api_key, self.api_secret)
                .with_identity(participant_identity)
                .with_name(participant_name or participant_identity)
                .with_grants(
                    VideoGrants(
                        room_join=True,
                        room=room_name,
                        **grants,
                    )
                )
                .with_ttl(timedelta(minutes=valid_minutes))
            )
            return cast(str, token.to_jwt())

        except ImportError:
            # Fallback using standard PyJWT
            import jwt

            now = datetime.now(UTC)
            payload = {
                "sub": participant_identity,
                "name": participant_name or participant_identity,
                "iss": self.api_key,
                "nbf": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=valid_minutes)).timestamp()),
                "video": {
                    "room": room_name,
                    "roomJoin": True,
                    "canPublish": grants["can_publish"],
                    "canSubscribe": grants["can_subscribe"],
                    "canPublishData": grants["can_publish_data"],
                    "canUpdateOwnMetadata": grants["can_update_own_metadata"],
                    "roomAdmin": grants["room_admin"],
                },
            }
            return cast(str, jwt.encode(payload, self.api_secret, algorithm="HS256"))
