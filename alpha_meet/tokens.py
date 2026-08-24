from datetime import datetime, timedelta, timezone

from alpha_core.config import settings


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
        is_admin: bool = False,
        valid_minutes: int = 120,
    ) -> str:
        """Generates a signed JWT token with video grants for the specified room."""
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
                        can_publish=True,
                        can_subscribe=True,
                        can_publish_data=True,
                        can_update_own_metadata=True,
                        room_admin=is_admin,
                    )
                )
                .with_ttl(timedelta(minutes=valid_minutes))
            )
            return token.to_jwt()

        except ImportError:
            # Fallback using standard PyJWT
            import jwt

            now = datetime.now(timezone.utc)
            payload = {
                "sub": participant_identity,
                "name": participant_name or participant_identity,
                "iss": self.api_key,
                "nbf": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=valid_minutes)).timestamp()),
                "video": {
                    "room": room_name,
                    "roomJoin": True,
                    "canPublish": True,
                    "canSubscribe": True,
                    "canPublishData": True,
                    "canUpdateOwnMetadata": True,
                    "roomAdmin": is_admin,
                },
            }
            return jwt.encode(payload, self.api_secret, algorithm="HS256")
