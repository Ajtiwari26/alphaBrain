import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from alpha_worker.adapters.vercel_adapter import VercelAdapter


@pytest.fixture
def adapter():
    return VercelAdapter(token="test_secret_token", project_id="test_project")


@pytest.mark.asyncio
async def test_deploy_preview_success(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    # Output includes the URL
    mock_process.communicate.return_value = (b"Deploying... https://test-app.vercel.app done.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        # Mock poll_status and check_health
        with patch.object(adapter, "poll_status", return_value="READY"):
            with patch.object(adapter, "check_health", return_value=True):
                result = await adapter.deploy_preview(Path("/tmp/worktree"))

                assert result.url == "https://test-app.vercel.app"
                assert result.status == "READY"
                assert result.health_ok is True
                mock_exec.assert_called_once_with(
                    "vercel", "--token", "test_secret_token", "--yes", "--cwd", "/tmp/worktree", "--project", "test_project",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )


@pytest.mark.asyncio
async def test_deploy_preview_failure_masks_token(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 1
    # Error message leaks the token
    mock_process.communicate.return_value = (b"", b"Error: invalid token test_secret_token!")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(RuntimeError, match="Vercel deployment failed: Error: invalid token \\*\\*\\*!"):
            await adapter.deploy_preview(Path("/tmp/worktree"))


@pytest.mark.asyncio
async def test_poll_status_success(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"State: READY", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        status = await adapter.poll_status("https://test-app.vercel.app", timeout_seconds=10)
        assert status == "READY"


@pytest.mark.asyncio
async def test_check_health_success(adapter):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.getcode.return_value = 200

        health_ok = await adapter.check_health("https://test-app.vercel.app")
        assert health_ok is True
