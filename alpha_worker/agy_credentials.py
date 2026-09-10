import asyncio
import fcntl
import logging
import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from alpha_core.config import settings

logger = logging.getLogger("alpha_worker.agy_credentials")

# Basic validation: alphanumeric, dash, dot, underscore, max 64 chars
ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._@-]{1,128}$")
TOKEN_PATTERN = re.compile(r"(ya29\.[A-Za-z0-9_-]+|AQ\.Ab[A-Za-z0-9_-]+|1//[A-Za-z0-9_-]+)")


class CredentialLockTimeoutError(Exception):
    pass


class IdentityMismatchError(Exception):
    pass


class SwitchCommandError(Exception):
    pass


class MalformedAccountError(Exception):
    pass


def redact_secrets(text: str) -> str:
    """Redacts common token patterns from output."""
    if not isinstance(text, str):
        return text
    return TOKEN_PATTERN.sub("[REDACTED]", text)


class SwitchRunner(Protocol):
    """Dependency injection boundary for account switching."""

    async def switch_account(self, account_id: str) -> None: ...

    async def verify_identity(self, expected_account_id: str) -> bool: ...


class LiveSwitchRunner:
    """Real implementation that calls agy-switch."""

    async def switch_account(self, account_id: str) -> None:
        # Pass --cli explicitly so we strictly mutate the CLI token for Opus without touching the IDE
        cmd = ["agy-switch", "switch", account_id, "--cli"]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Failed to switch account: {redact_secrets(stderr.decode())}")
            raise SwitchCommandError("Account switch command failed")

    async def verify_identity(self, expected_account_id: str) -> bool:
        cmd = ["agy-switch", "whoami"]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            return False

        # Simple extraction for now
        output = stdout.decode().strip()
        return expected_account_id in output


@dataclass
class GlobalCredentialLease:
    """A lease spanning the global OS lock for a specific profile."""

    account_id: str
    fd: int


@asynccontextmanager
async def acquire_credential_lease(
    account_id: str, runner: SwitchRunner | None = None
) -> AsyncGenerator[GlobalCredentialLease, None]:
    """
    Acquire global OS lock, switch profile, and verify identity.
    The lock remains held until the context manager exits.
    """
    if not ACCOUNT_ID_PATTERN.match(account_id):
        raise MalformedAccountError("Invalid account id format")

    runner = runner or LiveSwitchRunner()
    lock_path = settings.ROUTER_LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    timeout = settings.ROUTER_LOCK_TIMEOUT_SECONDS
    interval = 0.5

    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    locked = False

    elapsed = 0.0
    while elapsed < timeout:
        try:
            # Non-blocking lock attempt
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            break
        except (BlockingIOError, OSError):
            await asyncio.sleep(interval)
            elapsed += interval

    if not locked:
        os.close(fd)
        raise CredentialLockTimeoutError(
            f"Failed to acquire credential lock after {timeout} seconds"
        )

    try:
        # Perform switch and verify
        await runner.switch_account(account_id)
        identity_ok = await runner.verify_identity(account_id)
        if not identity_ok:
            raise IdentityMismatchError(f"Identity verification failed for {account_id}")

        yield GlobalCredentialLease(account_id=account_id, fd=fd)
    finally:
        # Guarantee lock release on any exception or normal exit
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)
