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
                import os
                env = os.environ.copy()
                env["VERCEL_TOKEN"] = "test_secret_token"
                mock_exec.assert_called_once_with(
                    "vercel", "--yes", "--cwd", "/tmp/worktree", "--project", "test_project",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
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

@pytest.mark.asyncio
async def test_poll_status_error(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"State: ERROR", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        status = await adapter.poll_status("https://test-app.vercel.app", timeout_seconds=10)
        assert status == "ERROR"

@pytest.mark.asyncio
async def test_poll_status_canceled(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"State: CANCELED", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        status = await adapter.poll_status("https://test-app.vercel.app", timeout_seconds=10)
        assert status == "CANCELED"

@pytest.mark.asyncio
async def test_poll_status_timeout(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    # Provide an output that doesn't match any state so it loops
    mock_process.communicate.return_value = (b"State: BUILDING", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        # fast timeout for test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            status = await adapter.poll_status("https://test-app.vercel.app", timeout_seconds=0)
            assert status == "TIMEOUT"

@pytest.mark.asyncio
async def test_poll_status_failure(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = (b"", b"Error: something went wrong")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(RuntimeError, match="Vercel inspect failed: Error: something went wrong"):
            await adapter.poll_status("https://test-app.vercel.app", timeout_seconds=10)

@pytest.mark.asyncio
async def test_check_health_exception(adapter):
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        health_ok = await adapter.check_health("https://test-app.vercel.app")
        assert health_ok is False

@pytest.mark.asyncio
async def test_deploy_preview_no_project_id():
    adapter = VercelAdapter(token="test_token")
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"Deploying... https://test-app.vercel.app done.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        with patch.object(adapter, "poll_status", return_value="READY"):
            with patch.object(adapter, "check_health", return_value=True):
                result = await adapter.deploy_preview(Path("/tmp/worktree"))
                assert result.url == "https://test-app.vercel.app"

                # Should not have --project in cmd
                import os
                env = os.environ.copy()
                env["VERCEL_TOKEN"] = "test_token"
                mock_exec.assert_called_once_with(
                    "vercel", "--yes", "--cwd", "/tmp/worktree",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )

@pytest.mark.asyncio
async def test_deploy_preview_url_in_stderr(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    # URL in stderr
    mock_process.communicate.return_value = (b"some output", b"Warning: deploying to https://test-app.vercel.app")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch.object(adapter, "poll_status", return_value="READY"):
            with patch.object(adapter, "check_health", return_value=True):
                result = await adapter.deploy_preview(Path("/tmp/worktree"))
                assert result.url == "https://test-app.vercel.app"

@pytest.mark.asyncio
async def test_deploy_preview_no_extractable_url(adapter):
    mock_process = AsyncMock()
    mock_process.returncode = 0
    # No URL
    mock_process.communicate.return_value = (b"Deploying...", b"No URL here")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(RuntimeError, match="Failed to extract deployment URL"):
            await adapter.deploy_preview(Path("/tmp/worktree"))
