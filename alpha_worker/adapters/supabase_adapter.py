import asyncio
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class DestructiveDDLError(Exception):
    """Raised when destructive DDL is detected."""

    pass


@dataclass
class MigrationStatus:
    applied_count: int
    pending_count: int | None
    is_healthy: bool


class SupabaseAdapter:
    def __init__(self, api_url: str, api_key: str):
        if not api_url:
            raise ValueError("Supabase API URL cannot be empty")
        if not api_key:
            raise ValueError("Supabase API key cannot be empty")
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _mask_secrets(self, text: str) -> str:
        if not self.api_key:
            return text
        return text.replace(self.api_key, "***")

    def _make_request(self, method: str, endpoint: str, data: bytes | None = None) -> Any:
        url = f"{self.api_url}{endpoint}"
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
        )
        if data:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                response_data = response.read()
                if not response_data:
                    return {}
                return json.loads(response_data.decode())
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode()
            except Exception:
                error_body = "Failed to read error body"
            error_msg = self._mask_secrets(error_body)
            raise RuntimeError(f"Supabase API error {e.code}: {error_msg}") from None
        except Exception as e:
            error_msg = self._mask_secrets(str(e))
            raise RuntimeError(f"Supabase API request failed: {error_msg}") from None

    async def check_health(self) -> bool:
        """Database health probe."""
        try:
            # A simple REST API call to check if the instance is up
            data = await asyncio.to_thread(self._make_request, "GET", "/rest/v1/")
            return data is not None
        except Exception as e:
            logger.debug(f"Health probe failed: {e}")
            return False

    def validate_ddl(self, sql: str) -> None:
        """Destructive DDL guardrails."""
        sql_upper = sql.upper()
        destructive_patterns = [
            r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW|ROLE|USER|INDEX|FUNCTION|TRIGGER|SEQUENCE|EXTENSION)\b",
            r"\bTRUNCATE\b",
            r"\bALTER\s+TABLE\s+.*?\bDROP\s+COLUMN\b",
        ]
        for pattern in destructive_patterns:
            if re.search(pattern, sql_upper, flags=re.DOTALL):
                raise DestructiveDDLError(f"Destructive DDL detected: {pattern}")

    async def get_migration_status(self) -> MigrationStatus:
        """Migration status inspection."""
        try:
            data = await asyncio.to_thread(self._make_request, "GET", "/rest/v1/schema_migrations")
            applied_count = len(data) if isinstance(data, list) else 0
            return MigrationStatus(applied_count=applied_count, pending_count=None, is_healthy=True)
        except Exception as e:
            raise RuntimeError(
                f"Failed to inspect migration status: {self._mask_secrets(str(e))}"
            ) from None
