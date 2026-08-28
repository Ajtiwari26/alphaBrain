from unittest.mock import patch

from fastapi.testclient import TestClient

from alpha_core.api.app import app

client = TestClient(app)


def test_liveness_check():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@patch("alpha_core.api.app.settings")
@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_check_failure(mock_get_session_factory, mock_settings):
    # Simulate production/staging environment where DB/migrations are required
    mock_settings.is_production = True
    mock_settings.is_staging = False

    # Make the session factory raise an exception to simulate DB unavailability
    mock_get_session_factory.side_effect = Exception("Database unavailable")

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}


@patch("alpha_core.api.app.settings")
@patch("alpha_core.db.connection.get_session_factory")
def test_liveness_independent_of_database(mock_get_session_factory, mock_settings):
    # Even if DB is down, liveness should work
    mock_get_session_factory.side_effect = Exception("Database unavailable")
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
