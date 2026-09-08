import urllib.error
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alpha_worker.adapters.render_adapter import RenderAdapter


@pytest.fixture
def adapter():
    return RenderAdapter(api_key="test_secret_key", service_id="srv_123")


def test_init_validation():
    with pytest.raises(ValueError, match="Render API key cannot be empty"):
        RenderAdapter(api_key="", service_id="srv_123")
    with pytest.raises(ValueError, match="Render service ID cannot be empty"):
        RenderAdapter(api_key="key", service_id="")


def test_mask_secrets(adapter):
    text = "Error: Invalid key test_secret_key here."
    assert adapter._mask_secrets(text) == "Error: Invalid key *** here."

    # Test when api_key is empty (shouldn't happen due to init validation, but good for coverage)
    adapter.api_key = ""
    assert adapter._mask_secrets(text) == text


@pytest.mark.asyncio
async def test_make_request_success(adapter):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"id": "dep_123"}'

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = adapter._make_request("GET", "/test")
        assert result == {"id": "dep_123"}

        # Test with data
        result_with_data = adapter._make_request("POST", "/test", data=b"{}")
        assert result_with_data == {"id": "dep_123"}


@pytest.mark.asyncio
async def test_make_request_http_error(adapter):
    mock_error = urllib.error.HTTPError(
        url="http://test", code=401, msg="Unauthorized", hdrs={}, fp=MagicMock()
    )
    mock_error.read = MagicMock(return_value=b'{"message": "Invalid token test_secret_key"}')

    with patch("urllib.request.urlopen", side_effect=mock_error):
        with pytest.raises(RuntimeError) as exc_info:
            adapter._make_request("GET", "/test")

        assert "Render API error 401" in str(exc_info.value)
        assert "Invalid token ***" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_request_general_exception(adapter):
    with patch("urllib.request.urlopen", side_effect=Exception("General error test_secret_key")):
        with pytest.raises(
            RuntimeError, match="Render API request failed: General error \\*\\*\\*"
        ):
            adapter._make_request("GET", "/test")


@pytest.mark.asyncio
async def test_get_service_url_success(adapter):
    with patch.object(
        adapter, "_make_request", return_value={"service": {"url": "https://test-app.onrender.com"}}
    ):
        url = await adapter._get_service_url()
        assert url == "https://test-app.onrender.com"

    with patch.object(
        adapter, "_make_request", return_value={"url": "https://test-app2.onrender.com"}
    ):
        url = await adapter._get_service_url()
        assert url == "https://test-app2.onrender.com"


@pytest.mark.asyncio
async def test_get_service_url_missing(adapter):
    with patch.object(adapter, "_make_request", return_value={"service": {}}):
        with pytest.raises(RuntimeError, match="Could not determine service URL"):
            await adapter._get_service_url()


@pytest.mark.asyncio
async def test_deploy_preview_success(adapter):
    with patch.object(adapter, "_make_request", return_value={"id": "dep_123"}) as mock_make:
        with patch.object(adapter, "poll_status", return_value="LIVE"):
            with patch.object(
                adapter, "_get_service_url", return_value="https://test-app.onrender.com"
            ):
                with patch.object(adapter, "check_health", return_value=True):
                    result = await adapter.deploy_preview()

                    assert result.url == "https://test-app.onrender.com"
                    assert result.status == "LIVE"
                    assert result.health_ok is True
                    mock_make.assert_called_once_with("POST", "/services/srv_123/deploys")


@pytest.mark.asyncio
async def test_deploy_preview_missing_id(adapter):
    with patch.object(adapter, "_make_request", return_value={"status": "created"}):
        with pytest.raises(RuntimeError, match="Failed to extract deploy ID"):
            await adapter.deploy_preview()


@pytest.mark.asyncio
async def test_poll_status_live(adapter):
    with patch.object(adapter, "_make_request", return_value={"status": "live"}):
        status = await adapter.poll_status("dep_123", timeout_seconds=10)
        assert status == "LIVE"


@pytest.mark.asyncio
async def test_poll_status_failed(adapter):
    with patch.object(adapter, "_make_request", return_value={"status": "build_failed"}):
        status = await adapter.poll_status("dep_123", timeout_seconds=10)
        assert status == "BUILD_FAILED"


@pytest.mark.asyncio
async def test_poll_status_timeout(adapter):
    with patch.object(adapter, "_make_request", return_value={"status": "created"}):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            status = await adapter.poll_status("dep_123", timeout_seconds=0)
            assert status == "TIMEOUT"


@pytest.mark.asyncio
async def test_check_health_success(adapter):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.getcode.return_value = 200

        health_ok = await adapter.check_health("https://test-app.onrender.com")
        assert health_ok is True


@pytest.mark.asyncio
async def test_check_health_exception(adapter):
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        health_ok = await adapter.check_health("https://test-app.onrender.com")
        assert health_ok is False
