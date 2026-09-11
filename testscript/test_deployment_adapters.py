from unittest.mock import MagicMock, patch

import pytest

from alpha_core.deployments.render_adapter import RenderAdapter
from alpha_core.deployments.rollback_pipeline import RollbackFailedError, RollbackPipeline
from alpha_core.deployments.vercel_adapter import VercelAdapter


@patch("alpha_core.deployments.vercel_adapter.requests.Session.post")
def test_vercel_trigger_deployment(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "dpl_123"}
    mock_post.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123", "proj123-name")
    deploy_id = adapter.trigger_deployment("main", "sha123")

    assert deploy_id == "dpl_123"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "https://api.vercel.com/v13/deployments" in args[0]
    assert kwargs["json"]["name"] == "proj123-name"
    assert kwargs["json"]["gitSource"]["ref"] == "main"
    assert kwargs["timeout"] == 30


@patch("alpha_core.deployments.vercel_adapter.requests.Session.post")
def test_vercel_trigger_deployment_missing_id(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_post.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123", "proj123-name")
    with pytest.raises(ValueError, match="Deployment ID missing"):
        adapter.trigger_deployment("main", "sha123")


@patch("alpha_core.deployments.vercel_adapter.requests.Session.get")
def test_vercel_poll_status(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"readyState": "READY"}
    mock_get.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123", "proj123-name")
    status = adapter.poll_status("dpl_123")

    assert status == "READY"
    _args, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 30


@patch("alpha_core.deployments.vercel_adapter.requests.Session.get")
def test_vercel_get_preview_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"url": "my-app.vercel.app"}
    mock_get.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123", "proj123-name")
    url = adapter.get_preview_url("dpl_123")

    assert url == "https://my-app.vercel.app"


@patch("alpha_core.deployments.vercel_adapter.requests.Session.get")
def test_vercel_get_preview_url_missing(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_get.return_value = mock_resp

    adapter = VercelAdapter("token", "proj123", "proj123-name")
    url = adapter.get_preview_url("dpl_123")
    assert url is None


@patch("alpha_core.deployments.vercel_adapter.requests.Session.post")
@patch("alpha_core.deployments.vercel_adapter.requests.Session.get")
def test_vercel_rollback(mock_get, mock_post):
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"jobStatus": "in_progress"}
    mock_post.return_value = mock_post_resp

    mock_get_resp1 = MagicMock()
    mock_get_resp1.json.return_value = {"jobStatus": "in_progress"}

    mock_get_resp2 = MagicMock()
    mock_get_resp2.json.return_value = {"jobStatus": "succeeded"}

    mock_get.side_effect = [mock_get_resp1, mock_get_resp2]

    adapter = VercelAdapter("token", "proj123", "proj123-name")
    pipeline = RollbackPipeline(adapter)

    with patch("time.sleep", return_value=None):
        new_id = pipeline.execute_rollback("dpl_123")

    assert new_id == "vercel_job:dpl_123"
    assert mock_get.call_count == 2


@patch("alpha_core.deployments.render_adapter.requests.Session.post")
def test_render_trigger_deployment(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "dep_123"}
    mock_post.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    deploy_id = adapter.trigger_deployment("main", "sha123")

    assert deploy_id == "dep_123"
    _args, kwargs = mock_post.call_args
    assert kwargs["json"]["commitId"] == "sha123"
    assert kwargs["timeout"] == 30


@patch("alpha_core.deployments.render_adapter.requests.Session.post")
def test_render_trigger_deployment_missing_id(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_post.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    with pytest.raises(ValueError, match="Deployment ID missing"):
        adapter.trigger_deployment("main", "sha123")


@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_render_poll_status(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "live"}
    mock_get.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    status = adapter.poll_status("dep_123")

    assert status == "READY"
    _args, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 30


@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_render_get_preview_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"serviceDetails": {"url": "https://my-app.onrender.com"}}
    mock_get.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    url = adapter.get_preview_url("dep_123")

    assert url == "https://my-app.onrender.com"


@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_render_get_preview_url_missing(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"serviceDetails": {}}
    mock_get.return_value = mock_resp

    adapter = RenderAdapter("key", "srv123")
    url = adapter.get_preview_url("dep_123")

    assert url is None


@patch("alpha_core.deployments.render_adapter.requests.Session.post")
@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_render_rollback(mock_get, mock_post):
    mock_get_resp = MagicMock()
    mock_get_resp.json.return_value = {"commit": {"id": "sha123"}}
    mock_get.return_value = mock_get_resp

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"id": "dep_456"}
    mock_post.return_value = mock_post_resp

    adapter = RenderAdapter("key", "srv123")
    new_id = adapter.rollback("dep_123")

    assert new_id == "dep_456"
    assert mock_post.call_args[1]["json"]["commitId"] == "sha123"


@patch("alpha_core.deployments.render_adapter.requests.Session.post")
@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_pipeline_polling(mock_get, mock_post):
    mock_get_resp1 = MagicMock()
    mock_get_resp1.json.return_value = {"commit": {"id": "sha123"}}

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"id": "dep_456"}
    mock_post.return_value = mock_post_resp

    mock_get_resp2 = MagicMock()
    mock_get_resp2.json.return_value = {"status": "live"}

    mock_get.side_effect = [mock_get_resp1, mock_get_resp2]

    adapter = RenderAdapter("key", "srv123")
    pipeline = RollbackPipeline(adapter)

    with patch("time.sleep", return_value=None):
        new_id = pipeline.execute_rollback("dep_123")
        assert new_id == "dep_456"


@patch("alpha_core.deployments.render_adapter.requests.Session.post")
@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_pipeline_polling_timeout(mock_get, mock_post):
    mock_get_resp1 = MagicMock()
    mock_get_resp1.json.return_value = {"commit": {"id": "sha123"}}

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"id": "dep_456"}
    mock_post.return_value = mock_post_resp

    mock_get_resp2 = MagicMock()
    mock_get_resp2.json.return_value = {"status": "in_progress"}

    mock_get.side_effect = [mock_get_resp1, mock_get_resp2, mock_get_resp2, mock_get_resp2, mock_get_resp2]

    adapter = RenderAdapter("key", "srv123")
    pipeline = RollbackPipeline(adapter)

    with patch("time.sleep", return_value=None), \
         patch("time.time", side_effect=[0, 10, 20, 310]):
        with pytest.raises(TimeoutError, match="Rollback timed out"):
            pipeline.execute_rollback("dep_123", timeout_seconds=300)


@patch("alpha_core.deployments.render_adapter.requests.Session.post")
@patch("alpha_core.deployments.render_adapter.requests.Session.get")
def test_pipeline_polling_failed(mock_get, mock_post):
    mock_get_resp1 = MagicMock()
    mock_get_resp1.json.return_value = {"commit": {"id": "sha123"}}

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"id": "dep_456"}
    mock_post.return_value = mock_post_resp

    mock_get_resp2 = MagicMock()
    mock_get_resp2.json.return_value = {"status": "update_failed"}

    mock_get.side_effect = [mock_get_resp1, mock_get_resp2]

    adapter = RenderAdapter("key", "srv123")
    pipeline = RollbackPipeline(adapter)

    with patch("time.sleep", return_value=None):
        with pytest.raises(RollbackFailedError, match="Rollback failed"):
            pipeline.execute_rollback("dep_123")
