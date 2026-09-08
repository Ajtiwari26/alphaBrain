import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import PORTAL_FRONTEND_DIR, app


@pytest.fixture
def client():
    return TestClient(app)

def test_portal_static_mount(client):
    """Test that the portal static directory is correctly mounted."""
    assert PORTAL_FRONTEND_DIR.exists(), "alpha_portal directory does not exist"

    response = client.get("/portal/")
    # HTMLResponse / StaticFiles default to index.html if html=True is passed
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    html = response.text
    # Check for Amazon-style milestone tracker
    assert "step-circle" in html
    assert "step-line" in html
    assert "Received" in html
    assert "In Progress" in html
    assert "Review" in html
    assert "Completed" in html

    # Check for dark mode responsive UI
    assert "dark" in html
    assert "tailwindcss" in html

    # Fetch portal.js to verify SSE logic
    js_response = client.get("/portal/portal.js")
    assert js_response.status_code == 200
    js_content = js_response.text

    # Check for SSE telemetry listener
    assert "EventSource(" in js_content
    assert "addEventListener('heartbeat'" in js_content or 'addEventListener("heartbeat"' in js_content
