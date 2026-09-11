from unittest.mock import MagicMock, patch

from alpha_core.deployments.render_adapter import RenderAdapter
from alpha_core.deployments.rollback_pipeline import RollbackPipeline
from alpha_core.deployments.vercel_adapter import VercelAdapter


@patch("alpha_core.deployments.vercel_adapter.requests.post")
def test_vercel_trigger_deployment(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "dpl_123"}
    mock_post.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123")
    deploy_id = adapter.trigger_deployment("main", "sha123")

    assert deploy_id == "dpl_123"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "https://api.vercel.com/v13/deployments" in args[0]
    assert kwargs["json"]["gitSource"]["ref"] == "main"

@patch("alpha_core.deployments.vercel_adapter.requests.get")
def test_vercel_poll_status(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"readyState": "READY"}
    mock_get.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123")
    status = adapter.poll_status("dpl_123")

    assert status == "READY"

@patch("alpha_core.deployments.vercel_adapter.requests.get")
def test_vercel_get_preview_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"url": "my-app.vercel.app"}
    mock_get.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123")
    url = adapter.get_preview_url("dpl_123")

    assert url == "https://my-app.vercel.app"

@patch("alpha_core.deployments.vercel_adapter.requests.post")
def test_vercel_rollback(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "dpl_456"}
    mock_post.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123")
    pipeline = RollbackPipeline(adapter)
    new_id = pipeline.execute_rollback("dpl_123")

    assert new_id == "dpl_456"

@patch("alpha_core.deployments.render_adapter.requests.post")
def test_render_trigger_deployment(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "dep_123"}
    mock_post.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    deploy_id = adapter.trigger_deployment("main", "sha123")

    assert deploy_id == "dep_123"

@patch("alpha_core.deployments.render_adapter.requests.get")
def test_render_poll_status(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "live"}
    mock_get.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    status = adapter.poll_status("dep_123")

    assert status == "READY"

@patch("alpha_core.deployments.render_adapter.requests.get")
def test_render_get_preview_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"serviceDetails": {"url": "https://my-app.onrender.com"}}
    mock_get.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    url = adapter.get_preview_url("dep_123")

    assert url == "https://my-app.onrender.com"
