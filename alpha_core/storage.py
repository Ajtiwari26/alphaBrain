"""
Alpha Brain Encrypted Object Storage & Signed URLs
===================================================
Provides production-ready interfaces for storing recordings, specs,
screenshots, logs, and builds with server-side encryption and short-lived signed URLs.
"""

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlencode

from alpha_core.config import settings

SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$")
ALLOWED_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/pdf",
        "application/zip",
        "application/octet-stream",
        "text/plain",
        "text/markdown",
        "text/csv",
        "image/png",
        "image/jpeg",
        "image/webp",
        "audio/wav",
        "audio/webm",
        "video/mp4",
        "video/webm",
    }
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class ObjectStorageError(Exception):
    """Base error for object storage operations."""


class ObjectStorageService:
    """Manages encrypted object storage and pre-signed access URLs."""

    def __init__(
        self,
        bucket_name: str = "alphabrain-artifacts",
        secret_key: str | None = None,
        base_url: str | None = None,
    ):
        self.bucket_name = bucket_name
        self.secret_key = (
            secret_key
            or settings.ALPHA_SIGNING_SECRET
            or "alphabrain-default-local-storage-secret-key"
        )
        self.base_url = (base_url or settings.PUBLIC_BASE_URL).rstrip("/")

    def sanitize_key(self, storage_key: str) -> str:
        """Sanitizes storage key to prevent directory traversal and special character exploits."""
        clean_key = storage_key.strip()
        if not clean_key:
            raise ObjectStorageError("Storage key cannot be empty")
        if clean_key.startswith("/"):
            raise ObjectStorageError("Storage key cannot be an absolute path")
        if not SAFE_KEY_PATTERN.match(clean_key):
            raise ObjectStorageError(f"Storage key contains illegal characters: {clean_key}")

        path = PurePosixPath(clean_key)
        if ".." in path.parts or path.is_absolute():
            raise ObjectStorageError("Storage key cannot contain path traversal")
        return clean_key

    def validate_media_type(self, media_type: str) -> str:
        """Ensures the uploaded artifact media type is allowlisted."""
        normalized = media_type.strip().lower().split(";")[0]
        if normalized not in ALLOWED_MEDIA_TYPES:
            raise ObjectStorageError(
                f"Media type '{media_type}' is not allowed for artifact storage"
            )
        return normalized

    def generate_signed_download_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 900,
    ) -> dict[str, Any]:
        """Generates a short-lived HMAC-signed download URL."""
        clean_key = self.sanitize_key(storage_key)
        ttl = max(60, min(expires_in_seconds, 86400))  # 1m to 24h
        expires_at = int((utc_now() + timedelta(seconds=ttl)).timestamp())

        message = f"GET\n{self.bucket_name}\n{clean_key}\n{expires_at}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        query = urlencode(
            {
                "expires": expires_at,
                "signature": signature,
                "bucket": self.bucket_name,
            }
        )
        url = f"{self.base_url}/api/storage/download/{clean_key}?{query}"

        return {
            "url": url,
            "storage_key": clean_key,
            "expires_at": expires_at,
            "encryption": "AES256",
        }

    def generate_signed_upload_url(
        self,
        storage_key: str,
        media_type: str,
        expires_in_seconds: int = 900,
    ) -> dict[str, Any]:
        """Generates a short-lived HMAC-signed upload URL requiring server-side encryption."""
        clean_key = self.sanitize_key(storage_key)
        clean_media_type = self.validate_media_type(media_type)
        ttl = max(60, min(expires_in_seconds, 3600))  # 1m to 1h
        expires_at = int((utc_now() + timedelta(seconds=ttl)).timestamp())

        message = f"PUT\n{self.bucket_name}\n{clean_key}\n{clean_media_type}\n{expires_at}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        query = urlencode(
            {
                "expires": expires_at,
                "signature": signature,
                "media_type": clean_media_type,
                "bucket": self.bucket_name,
            }
        )
        url = f"{self.base_url}/api/storage/upload/{clean_key}?{query}"

        return {
            "url": url,
            "storage_key": clean_key,
            "media_type": clean_media_type,
            "expires_at": expires_at,
            "required_headers": {
                "Content-Type": clean_media_type,
                "x-amz-server-side-encryption": "AES256",
            },
        }

    def verify_signed_url(
        self,
        method: str,
        storage_key: str,
        expires_at: int,
        signature: str,
        media_type: str | None = None,
    ) -> bool:
        """Validates the cryptographic signature and expiration of a signed URL."""
        if utc_now().timestamp() > expires_at:
            return False

        clean_key = self.sanitize_key(storage_key)
        if method.upper() == "GET":
            message = f"GET\n{self.bucket_name}\n{clean_key}\n{expires_at}"
        elif method.upper() == "PUT":
            if not media_type:
                return False
            clean_media_type = self.validate_media_type(media_type)
            message = f"PUT\n{self.bucket_name}\n{clean_key}\n{clean_media_type}\n{expires_at}"
        else:
            return False

        expected_sig = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_sig)


storage_service = ObjectStorageService()
