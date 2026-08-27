import asyncio
import fcntl
import os

import pytest

from alpha_core.config import settings
from alpha_worker.agy_credentials import (
    CredentialLockTimeoutError,
    IdentityMismatchError,
    MalformedAccountError,
    SwitchCommandError,
    SwitchRunner,
    acquire_credential_lease,
    redact_secrets,
)


class FakeRunner(SwitchRunner):
    def __init__(self, switch_fails=False, verify_fails=False, token_output=False):
        self.switch_fails = switch_fails
        self.verify_fails = verify_fails
        self.token_output = token_output
        self.switched_to = None

    async def switch_account(self, account_id: str) -> None:
        if self.token_output:
            raise SwitchCommandError(redact_secrets("Failed auth with token ya29.SECRET12345"))
        if self.switch_fails:
            raise SwitchCommandError("Simulated switch failure")
        self.switched_to = account_id

    async def verify_identity(self, expected_account_id: str) -> bool:
        if self.verify_fails:
            return False
        return self.switched_to == expected_account_id


@pytest.fixture
def tmp_lock(tmp_path):
    lock_file = tmp_path / "test_router-lock.lck"
    old_lock = settings.ROUTER_LOCK_PATH
    settings.ROUTER_LOCK_PATH = lock_file
    yield lock_file
    settings.ROUTER_LOCK_PATH = old_lock


@pytest.mark.asyncio
async def test_mutual_exclusion(tmp_lock):
    settings.ROUTER_LOCK_TIMEOUT_SECONDS = 1
    runner = FakeRunner()

    # Hold the lock manually
    fd = os.open(tmp_lock, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    try:
        with pytest.raises(CredentialLockTimeoutError):
            async with acquire_credential_lease("test_account", runner=runner):
                pass
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@pytest.mark.asyncio
async def test_wrong_identity(tmp_lock):
    runner = FakeRunner(verify_fails=True)
    with pytest.raises(IdentityMismatchError):
        async with acquire_credential_lease("test_account", runner=runner):
            pass


@pytest.mark.asyncio
async def test_switch_failure(tmp_lock):
    runner = FakeRunner(switch_fails=True)
    with pytest.raises(SwitchCommandError):
        async with acquire_credential_lease("test_account", runner=runner):
            pass


@pytest.mark.asyncio
async def test_redaction(tmp_lock):
    runner = FakeRunner(token_output=True)
    try:
        async with acquire_credential_lease("test_account", runner=runner):
            pass
    except SwitchCommandError as e:
        assert "ya29." not in str(e)
        assert "[REDACTED]" in str(e)


@pytest.mark.asyncio
async def test_malformed_account(tmp_lock):
    runner = FakeRunner()
    with pytest.raises(MalformedAccountError):
        async with acquire_credential_lease("test;rm -rf /", runner=runner):
            pass

    with pytest.raises(MalformedAccountError):
        async with acquire_credential_lease("test account", runner=runner):
            pass


@pytest.mark.asyncio
async def test_exception_releases_lock(tmp_lock):
    runner = FakeRunner()
    try:
        async with acquire_credential_lease("test_account", runner=runner):
            raise ValueError("Intentional crash")
    except ValueError:
        pass

    # Should be able to acquire it immediately after
    async with acquire_credential_lease("test_account", runner=runner):
        pass


@pytest.mark.asyncio
async def test_cancellation_releases_lock(tmp_lock):
    runner = FakeRunner()

    async def worker():
        async with acquire_credential_lease("test_account", runner=runner):
            await asyncio.sleep(10)

    task = asyncio.create_task(worker())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should be able to acquire it immediately after
    async with acquire_credential_lease("test_account", runner=runner):
        pass
