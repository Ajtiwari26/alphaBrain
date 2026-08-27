"""
alpha_core/logging_config.py
Structured and secret-redacted logging configuration for Alpha Brain.
Provides both human-readable redacting formatters (development/test)
and structured JSON formatters (staging/production).
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from alpha_core.security import redact_dict, redact_secrets


class RedactingFormatter(logging.Formatter):
    """Log formatter that scrubs sensitive credentials from plain-text log lines."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_secrets(formatted)


class StructuredJsonFormatter(logging.Formatter):
    """Log formatter producing JSON lines with automatic secret scrubbing."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(message),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = redact_secrets(self.formatException(record.exc_info))
        if hasattr(record, "extra") and isinstance(record.extra, dict):  # type: ignore[attr-defined]
            log_entry["extra"] = redact_dict(record.extra)  # type: ignore[attr-defined]

        return json.dumps(log_entry, separators=(",", ":"))


def setup_logging(
    env: str = "development",
    log_level: str = "INFO",
    json_format: bool | None = None,
) -> None:
    """Configures global logging with the appropriate redacting formatter."""
    use_json = json_format if json_format is not None else env in ("production", "staging")
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if use_json:
        formatter: logging.Formatter = StructuredJsonFormatter()
    else:
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
