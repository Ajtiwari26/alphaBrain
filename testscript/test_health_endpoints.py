from unittest.mock import AsyncMock, MagicMock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from alpha_core.api.app import app
from alpha_core.config import settings

client = TestClient(app)


def test_liveness_check():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_exact_match(mock_get_session_factory):
    mock_session = AsyncMock()
    # Mocking rows returned by SELECT version_num FROM alembic_version
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [settings.EXPECTED_ALEMBIC_REVISION]
    mock_session.execute.side_effect = [None, mock_res]

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_get_session_factory.return_value = mock_factory

    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_missing_table(mock_get_session_factory):
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [None, OperationalError("no such table", None, None)]

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_get_session_factory.return_value = mock_factory

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}

    resp_text = response.text.lower()
    for secret in ["ea716532600e", "url", "password", "token", "exception", "operationalerror"]:
        assert secret not in resp_text


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_empty_revision(mock_get_session_factory):
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_session.execute.side_effect = [None, mock_res]

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_get_session_factory.return_value = mock_factory

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_older_revision(mock_get_session_factory):
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = ["e7a9c2f4d601"]
    mock_session.execute.side_effect = [None, mock_res]

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_get_session_factory.return_value = mock_factory

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_unknown_revision(mock_get_session_factory):
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = ["unknown_future_rev"]
    mock_session.execute.side_effect = [None, mock_res]

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_get_session_factory.return_value = mock_factory

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_multiple_rows(mock_get_session_factory):
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = ["ea716532600e", "e7a9c2f4d601"]
    mock_session.execute.side_effect = [None, mock_res]

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_get_session_factory.return_value = mock_factory

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}


@patch("alpha_core.db.connection.get_session_factory")
def test_readiness_database_outage(mock_get_session_factory):
    mock_get_session_factory.side_effect = Exception("Database unavailable")

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service Unavailable"}

    resp_text = response.text.lower()
    for secret in ["password", "token", "exception", "database"]:
        assert secret not in resp_text


@patch("alpha_core.db.connection.get_session_factory")
def test_liveness_independent_of_database(mock_get_session_factory):
    mock_get_session_factory.side_effect = Exception("Database unavailable")
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_expected_revision_matches_alembic_head():
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    assert head == settings.EXPECTED_ALEMBIC_REVISION
