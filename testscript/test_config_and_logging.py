"""
testscript/test_config_and_logging.py
Automated tests for environment profile configuration, safety validation,
structured logging with secret scrubbing, and CI / pre-commit YAML specifications.
"""

import json
import logging
from pathlib import Path

import pytest
import yaml

from alpha_core.config import AppEnvironment, Settings
from alpha_core.logging_config import RedactingFormatter, StructuredJsonFormatter, setup_logging
from alpha_core.security import REDACTED


class TestEnvironmentConfiguration:
    def test_environment_profiles(self):
        dev_settings = Settings(ENV="development")
        assert dev_settings.is_development is True
        assert dev_settings.is_production is False
        assert dev_settings.is_staging is False
        assert dev_settings.is_test is False

        prod_settings = Settings(ENV="production")
        assert prod_settings.is_production is True
        assert prod_settings.is_development is False

        staging_settings = Settings(ENV="staging")
        assert staging_settings.is_staging is True

        test_settings = Settings(ENV="test")
        assert test_settings.is_test is True

    def test_development_environment_validation_passes(self):
        dev_settings = Settings(
            ENV=AppEnvironment.DEVELOPMENT.value,
            DEBUG=True,
            DATABASE_URL="sqlite+aiosqlite:///alpha_brain.db",
            WORKER_ALLOW_LOCAL_DB=True,
        )
        issues = dev_settings.validate_environment_safety()
        assert len(issues) == 0

    def test_production_environment_safety_validation(self):
        # Insecure production config
        insecure_prod = Settings(
            ENV=AppEnvironment.PRODUCTION.value,
            DEBUG=True,
            DATABASE_URL="sqlite+aiosqlite:///alpha_brain.db",
            WORKER_ALLOW_LOCAL_DB=True,
            ALPHA_API_TOKEN="short",
            ALPHA_WORKER_TOKEN="short",
            ALPHA_SIGNING_SECRET="short",
            CORS_ORIGINS=("*",),
        )
        issues = insecure_prod.validate_environment_safety()
        assert any("DEBUG must be false" in issue for issue in issues)
        assert any("cannot use SQLite" in issue for issue in issues)
        assert any("WORKER_ALLOW_LOCAL_DB must be false" in issue for issue in issues)
        assert any("ALPHA_API_TOKEN must be at least 32" in issue for issue in issues)
        assert any("Wildcard CORS origin" in issue for issue in issues)

        with pytest.raises(ValueError, match="Environment validation failed"):
            insecure_prod.validate_environment_safety(strict=True)

    def test_valid_production_environment_validation(self):
        valid_prod = Settings(
            ENV=AppEnvironment.PRODUCTION.value,
            DEBUG=False,
            DATABASE_URL="postgresql+psycopg://user:password@prod-db.example.com:5432/alphabrain",
            WORKER_ALLOW_LOCAL_DB=False,
            ALPHA_API_TOKEN="prod-api-token-with-at-least-32-chars-long",
            ALPHA_WORKER_TOKEN="prod-worker-token-with-at-least-32-chars-long",
            ALPHA_SIGNING_SECRET="prod-signing-secret-with-at-least-32-chars-long",
            CORS_ORIGINS=("https://alphabrain.example.com",),
        )
        issues = valid_prod.validate_environment_safety(strict=True)
        assert len(issues) == 0


class TestStructuredLogging:
    def test_redacting_formatter_scrubs_secrets(self):
        formatter = RedactingFormatter(fmt="%(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User login failed with token=secret_auth_token_value_12345",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        assert REDACTED in formatted
        assert "secret_auth_token_value_12345" not in formatted

    def test_structured_json_formatter_produces_scrubbed_json(self):
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="auth_service",
            level=logging.WARNING,
            pathname=__file__,
            lineno=42,
            msg="Database authentication failed for user=operator with password: synthetic_password_value",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["level"] == "WARNING"
        assert parsed["logger"] == "auth_service"
        assert parsed["line"] == 42
        assert "timestamp" in parsed
        assert REDACTED in parsed["message"]
        assert "synthetic_password_value" not in parsed["message"]

    def test_setup_logging_configures_root_logger(self):
        setup_logging(env="production", log_level="DEBUG", json_format=True)
        root = logging.getLogger()
        assert len(root.handlers) > 0
        assert isinstance(root.handlers[0].formatter, StructuredJsonFormatter)

        # Restore development logger
        setup_logging(env="development", log_level="INFO", json_format=False)
        assert isinstance(root.handlers[0].formatter, RedactingFormatter)


class TestCIAndPreCommitSpecifications:
    def test_ci_workflow_yaml_is_valid_and_non_secret(self):
        ci_path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), "CI workflow file .github/workflows/ci.yml must exist"

        content = ci_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        assert "jobs" in parsed
        jobs = parsed["jobs"]
        assert "lint-and-format" in jobs
        assert "type-check" in jobs
        assert "unit-tests" in jobs
        assert "secret-scan" in jobs

        # Ensure no live account substrings are hardcoded in CI YAML
        assert "AQ.Ab8" not in content

    def test_pre_commit_config_yaml_is_valid(self):
        config_path = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"
        assert config_path.exists(), ".pre-commit-config.yaml must exist"

        content = config_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        assert "repos" in parsed
        hook_ids = [hook["id"] for repo in parsed["repos"] for hook in repo.get("hooks", [])]
        assert "ruff" in hook_ids
        assert "ruff-format" in hook_ids
        assert "mypy" in hook_ids
        assert "pytest-quick" in hook_ids


def test_worker_lease_duration_bounds():
    from pydantic import ValidationError

    from alpha_core.config import Settings

    # Valid
    s = Settings(WORKER_LEASE_DURATION_SECONDS=1800)
    assert s.WORKER_LEASE_DURATION_SECONDS == 1800

    # Invalid low
    with pytest.raises(
        ValidationError,
        match="WORKER_LEASE_DURATION_SECONDS must be between 300 and 7200",
    ):
        Settings(WORKER_LEASE_DURATION_SECONDS=299)

    # Invalid high
    with pytest.raises(
        ValidationError,
        match="WORKER_LEASE_DURATION_SECONDS must be between 300 and 7200",
    ):
        Settings(WORKER_LEASE_DURATION_SECONDS=7201)


def test_task_progress_stall_timeout_bounds():
    from pydantic import ValidationError

    from alpha_core.config import Settings

    assert (
        Settings(TASK_PROGRESS_STALL_TIMEOUT_SECONDS=300).TASK_PROGRESS_STALL_TIMEOUT_SECONDS == 300
    )
    with pytest.raises(
        ValidationError,
        match="TASK_PROGRESS_STALL_TIMEOUT_SECONDS must be between 60 and 7200",
    ):
        Settings(TASK_PROGRESS_STALL_TIMEOUT_SECONDS=59)
    with pytest.raises(
        ValidationError,
        match="TASK_PROGRESS_STALL_TIMEOUT_SECONDS must be between 60 and 7200",
    ):
        Settings(TASK_PROGRESS_STALL_TIMEOUT_SECONDS=7201)
