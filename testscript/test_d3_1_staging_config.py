import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from alpha_core.api.app import app
from alpha_core.config import Settings

client = TestClient(app)


def test_staging_rejects_sqlite():
    settings = Settings(
        ENV="staging",
        DATABASE_URL="sqlite+aiosqlite:///test.db",
        WORKER_ALLOW_LOCAL_DB=False,
        ALPHA_API_TOKEN="a" * 32,
        ALPHA_WORKER_TOKEN="a" * 32,
        ALPHA_SIGNING_SECRET="a" * 32,
    )
    issues = settings.validate_environment_safety()
    assert any("cannot use SQLite and must use PostgreSQL" in issue for issue in issues)


def test_staging_rejects_local_worker_db_mode():
    settings = Settings(
        ENV="staging",
        DATABASE_URL="postgresql://user:pass@host/db",
        WORKER_ALLOW_LOCAL_DB=True,
        ALPHA_API_TOKEN="a" * 32,
        ALPHA_WORKER_TOKEN="a" * 32,
        ALPHA_SIGNING_SECRET="a" * 32,
    )
    issues = settings.validate_environment_safety()
    assert any("WORKER_ALLOW_LOCAL_DB must be false" in issue for issue in issues)


def test_staging_rejects_enabled_agy_execution_on_render():
    with patch.dict(os.environ, {"RENDER": "true"}):
        settings = Settings(
            ENV="staging",
            DATABASE_URL="postgresql://user:pass@host/db",
            WORKER_ALLOW_LOCAL_DB=False,
            ALPHA_API_TOKEN="a" * 32,
            ALPHA_WORKER_TOKEN="a" * 32,
            ALPHA_SIGNING_SECRET="a" * 32,
            ANTIGRAVITY_EXECUTION_ENABLED=True,
        )
        issues = settings.validate_environment_safety()
        assert any(
            "ANTIGRAVITY_EXECUTION_ENABLED must be false on Render" in issue for issue in issues
        )


def test_staging_rejects_missing_required_secrets():
    settings = Settings(
        ENV="staging",
        DATABASE_URL="postgresql://user:pass@host/db",
        WORKER_ALLOW_LOCAL_DB=False,
        ALPHA_API_TOKEN="short",
        ALPHA_WORKER_TOKEN="short",
        ALPHA_SIGNING_SECRET="",
    )
    issues = settings.validate_environment_safety()
    assert any("ALPHA_API_TOKEN must be at least 32 characters" in issue for issue in issues)
    assert any("ALPHA_WORKER_TOKEN must be at least 32 characters" in issue for issue in issues)
    assert any("ALPHA_SIGNING_SECRET must be at least 32 characters" in issue for issue in issues)


def test_validation_errors_redact_values():
    settings = Settings(
        ENV="staging",
        DATABASE_URL="postgresql://user:secretpass123@host/db",
        WORKER_ALLOW_LOCAL_DB=False,
        ALPHA_API_TOKEN="short",
        ALPHA_WORKER_TOKEN="short",
        ALPHA_SIGNING_SECRET="short",
    )
    issues = settings.validate_environment_safety()
    for issue in issues:
        assert "secretpass123" not in issue


def test_liveness_works_without_agy():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_fails_safely_on_db_outage():
    with patch("alpha_core.db.connection.get_session_factory") as mock_factory:
        mock_factory.side_effect = Exception("DB Connection Refused")
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Service Unavailable"}


def test_readiness_succeeds_with_valid_db_stub():
    class MockSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def execute(self, statement):
            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = ["58b5b056d9e3"]
            return mock_res

    with patch("alpha_core.db.connection.get_session_factory") as mock_factory:
        mock_factory.return_value = lambda: MockSession()
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_error_responses_reveal_no_secrets():
    with patch("alpha_core.db.connection.get_session_factory") as mock_factory:
        mock_factory.side_effect = Exception("SuperSecretPassword123")
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "SuperSecretPassword123" not in response.text


def test_existing_development_mode_remains_usable_locally():
    settings = Settings(
        ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///alpha_brain.db",
        WORKER_ALLOW_LOCAL_DB=True,
    )
    issues = settings.validate_environment_safety()
    assert len(issues) == 0
