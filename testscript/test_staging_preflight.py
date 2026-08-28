from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from alpha_core.db.connection import init_db

ROOT_DIR = Path(__file__).parent.parent


@pytest.mark.asyncio
async def test_init_db_no_migrations_in_staging():
    with (
        patch("alpha_core.db.connection.settings.ENV", "staging"),
        patch(
            "alpha_core.db.connection.run_alembic_migrations", new_callable=AsyncMock
        ) as mock_migrations,
        patch("alpha_core.db.connection.get_engine") as mock_engine,
    ):
        await init_db()
        mock_migrations.assert_not_called()
        mock_engine.assert_not_called()


@pytest.mark.asyncio
async def test_init_db_no_migrations_in_production():
    with (
        patch("alpha_core.db.connection.settings.ENV", "production"),
        patch(
            "alpha_core.db.connection.run_alembic_migrations", new_callable=AsyncMock
        ) as mock_migrations,
        patch("alpha_core.db.connection.get_engine") as mock_engine,
    ):
        await init_db()
        mock_migrations.assert_not_called()
        mock_engine.assert_not_called()


class MockAsyncContextManager:
    def __init__(self, obj):
        self.obj = obj

    async def __aenter__(self):
        return self.obj

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_init_db_development_behavior():
    from unittest.mock import MagicMock

    with (
        patch("alpha_core.db.connection.settings.ENV", "development"),
        patch("alpha_core.db.connection.settings.DATABASE_URL", "sqlite+aiosqlite:///:memory:"),
        patch("alpha_core.db.connection.get_engine") as mock_get_engine,
    ):
        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value = MockAsyncContextManager(mock_conn)
        mock_get_engine.return_value = mock_engine

        await init_db()
        mock_get_engine.assert_called_once()
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()


def test_render_yaml_configuration():
    render_path = ROOT_DIR / "render.yaml"
    with open(render_path) as f:
        config = yaml.safe_load(f)

    web_service = next(s for s in config["services"] if s["type"] == "web")

    assert web_service["name"] == "alpha-brain-staging"
    assert web_service["healthCheckPath"] == "/health/ready"
    assert web_service["autoDeploy"] is False
    assert "alembic" not in web_service.get("buildCommand", "")
    assert "alembic" not in web_service.get("startCommand", "")

    env_vars = {env["key"]: env.get("value") for env in web_service["envVars"] if "value" in env}
    assert env_vars.get("ENV") == "staging"
    assert env_vars.get("ANTIGRAVITY_EXECUTION_ENABLED") == "false"
    assert env_vars.get("WORKER_ALLOW_LOCAL_DB") == "false"


def test_operations_guide_no_auto_deploy_or_startup_migration():
    guide_path = ROOT_DIR / "docs" / "operations" / "render-supabase-setup.md"
    with open(guide_path) as f:
        content = f.read()

    # Assert contradictory Auto-Deploy is removed
    assert "Auto-Deploy: Yes" not in content

    # Assert no startup migration guidance
    assert "runs Alembic migrations" not in content
    assert "must never** run Alembic migrations" in content
