import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.local")
load_dotenv(PROJECT_ROOT / ".env")
USE_VERTEX = os.getenv("GEMINI_USE_VERTEX", "false").lower() == "true"


class AppEnvironment(str, Enum):
    """Supported operating environments for Alpha Brain."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def _csv_env(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


class Settings(BaseModel):
    # App Information
    APP_NAME: str = "Alpha Brain"
    ENV: str = os.getenv("ENV", AppEnvironment.DEVELOPMENT.value)
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Environment profile helpers
    @property
    def is_development(self) -> bool:
        return self.ENV.lower() == AppEnvironment.DEVELOPMENT.value

    @property
    def is_test(self) -> bool:
        return self.ENV.lower() == AppEnvironment.TEST.value

    @property
    def is_staging(self) -> bool:
        return self.ENV.lower() == AppEnvironment.STAGING.value

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == AppEnvironment.PRODUCTION.value

    def validate_environment_safety(self, strict: bool = False) -> list[str]:
        """Validate safety constraints for staging and production environments."""
        issues: list[str] = []
        if self.is_production or self.is_staging:
            if self.DEBUG:
                issues.append(f"DEBUG must be false in {self.ENV} environment")
            if self.WORKER_ALLOW_LOCAL_DB:
                issues.append(f"WORKER_ALLOW_LOCAL_DB must be false in {self.ENV} environment")

            db_url_lower = self.DATABASE_URL.lower()
            if "sqlite" in db_url_lower or not (
                db_url_lower.startswith("postgres://")
                or db_url_lower.startswith("postgresql://")
                or db_url_lower.startswith("postgresql+")
            ):
                issues.append("Production database URL cannot use SQLite and must use PostgreSQL")

            if not self.ALPHA_API_TOKEN or len(self.ALPHA_API_TOKEN) < 32:
                issues.append(f"ALPHA_API_TOKEN must be at least 32 characters in {self.ENV}")
            if not self.ALPHA_WORKER_TOKEN or len(self.ALPHA_WORKER_TOKEN) < 32:
                issues.append(f"ALPHA_WORKER_TOKEN must be at least 32 characters in {self.ENV}")
            if not self.ALPHA_SIGNING_SECRET or len(self.ALPHA_SIGNING_SECRET) < 32:
                issues.append(f"ALPHA_SIGNING_SECRET must be at least 32 characters in {self.ENV}")
            if any(origin == "*" for origin in self.CORS_ORIGINS):
                issues.append(f"Wildcard CORS origin '*' is forbidden in {self.ENV}")
            if os.getenv("RENDER") == "true" and self.ANTIGRAVITY_EXECUTION_ENABLED:
                issues.append(
                    f"ANTIGRAVITY_EXECUTION_ENABLED must be false on Render in {self.ENV}"
                )
            if self.WORKER_CONTROL_PLANE_URL and (
                "localhost" in self.WORKER_CONTROL_PLANE_URL
                or "127.0.0.1" in self.WORKER_CONTROL_PLANE_URL
            ):
                issues.append(f"WORKER_CONTROL_PLANE_URL cannot point to localhost in {self.ENV}")
        if strict and issues:
            raise ValueError(
                f"Environment validation failed for '{self.ENV}': " + "; ".join(issues)
            )
        return issues

    # Authentication and network boundaries
    ALPHA_API_TOKEN: str = os.getenv("ALPHA_API_TOKEN", "")
    ALPHA_WORKER_TOKEN: str = os.getenv("ALPHA_WORKER_TOKEN", "")
    ALPHA_SIGNING_SECRET: str = os.getenv("ALPHA_SIGNING_SECRET", "")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    CORS_ORIGINS: tuple[str, ...] = _csv_env(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    )

    # AI Model Credentials (Provided by User)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    GEMINI_USE_VERTEX: bool = USE_VERTEX
    GOOGLE_CLOUD_PROJECT: str = os.getenv(
        "GOOGLE_CLOUD_PROJECT",
        os.getenv("GCP_PROJECT", ""),
    )
    GOOGLE_CLOUD_LOCATION: str = os.getenv(
        "GOOGLE_CLOUD_LOCATION",
        os.getenv("GCP_LOCATION", "us-central1"),
    )
    GEMINI_LIVE_MODEL: str = os.getenv(
        "GEMINI_LIVE_MODEL",
        (
            "gemini-live-2.5-flash-native-audio"
            if USE_VERTEX
            else "gemini-2.5-flash-native-audio-latest"
        ),
    )
    GEMINI_LIVE_VOICE: str = os.getenv("GEMINI_LIVE_VOICE", "Aoede")

    # Telephony (Plivo Credentials provided by User)
    PLIVO_AUTH_ID: str = os.getenv("PLIVO_AUTH_ID", "")
    PLIVO_AUTH_TOKEN: str = os.getenv("PLIVO_AUTH_TOKEN", "")
    PLIVO_PHONE_NUMBER: str = os.getenv("PLIVO_PHONE_NUMBER", "")

    # Stitch MCP Configuration (Ajay's Connected Account)
    STITCH_MODEL_ID: str = "gemini-3.1-pro"

    # Database Configuration (Local SQLite or Postgres)
    EXPECTED_ALEMBIC_REVISION: str = "ea716532600e"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///" + str(Path(__file__).resolve().parent.parent / "alpha_brain.db"),
    )

    # Local Temporal Orchestrator
    TEMPORAL_HOST: str = os.getenv("TEMPORAL_HOST", "localhost:7233")
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")

    # Local Paths & Hardware
    WORKSPACE_ROOT: Path = PROJECT_ROOT
    MEMORY_GRAPH_PATH: Path = Path(
        os.getenv("MEMORY_GRAPH_PATH", "/Users/ajaytiwari/Desktop/Projects/memory_graph")
    )
    CLIENT_PROJECTS_ROOT: Path = Path(
        os.getenv("CLIENT_PROJECTS_ROOT", "/Users/ajaytiwari/Desktop/Projects/clientProjects")
    )
    ANTIGRAVITY_EXECUTION_ENABLED: bool = (
        os.getenv("ANTIGRAVITY_EXECUTION_ENABLED", "true").lower() == "true"
    )
    ANTIGRAVITY_MODEL: str = os.getenv("ANTIGRAVITY_MODEL", "gemini-3.1-pro-high")
    ANTIGRAVITY_UNATTENDED_COMMANDS: bool = (
        os.getenv("ANTIGRAVITY_UNATTENDED_COMMANDS", "false").lower() == "true"
    )
    ANTIGRAVITY_EFFORT: str = os.getenv("ANTIGRAVITY_EFFORT", "high")

    # Model Routing (Packet R2-A)
    MODEL_ROUTING_ENABLED: bool = os.getenv("MODEL_ROUTING_ENABLED", "false").lower() == "true"
    ROUTER_STATE_PATH: Path = Path(
        os.getenv(
            "ROUTER_STATE_PATH",
            str(
                Path.home() / "Library" / "Application Support" / "AlphaBrain" / "router-state.json"
            ),
        )
    )
    ROUTER_LOCK_PATH: Path = Path(
        os.getenv(
            "ROUTER_LOCK_PATH",
            str(Path.home() / "Library" / "Application Support" / "AlphaBrain" / "router-lock.lck"),
        )
    )
    ROUTER_LOCK_TIMEOUT_SECONDS: int = int(os.getenv("ROUTER_LOCK_TIMEOUT_SECONDS", "300"))
    ROUTER_INFERRED_COOLDOWN_HOURS: int = int(os.getenv("ROUTER_INFERRED_COOLDOWN_HOURS", "5"))
    MAX_ELIGIBLE_ATTEMPTS: int = int(os.getenv("MAX_ELIGIBLE_ATTEMPTS", "5"))

    @model_validator(mode="after")
    def validate_timing_boundaries(self) -> "Settings":
        # Validate maximums
        if self.WORKER_LEASE_DURATION_SECONDS > 7200:
            raise ValueError("WORKER_LEASE_DURATION_SECONDS must be <= 7200")
        if self.TASK_PROGRESS_STALL_TIMEOUT_SECONDS > 7200:
            raise ValueError("TASK_PROGRESS_STALL_TIMEOUT_SECONDS must be <= 7200")
        if self.TASK_WATCHDOG_SCAN_INTERVAL_SECONDS > 3600:
            raise ValueError("TASK_WATCHDOG_SCAN_INTERVAL_SECONDS must be <= 3600")

        # Validate minimums
        if self.is_production or self.is_staging:
            if self.WORKER_LEASE_DURATION_SECONDS < 300:
                raise ValueError(
                    "WORKER_LEASE_DURATION_SECONDS must be >= 300 in production/staging"
                )
            if self.TASK_PROGRESS_STALL_TIMEOUT_SECONDS < 60:
                raise ValueError(
                    "TASK_PROGRESS_STALL_TIMEOUT_SECONDS must be >= 60 in production/staging"
                )
            if self.TASK_WATCHDOG_SCAN_INTERVAL_SECONDS < 5:
                raise ValueError(
                    "TASK_WATCHDOG_SCAN_INTERVAL_SECONDS must be >= 5 in production/staging"
                )
        elif self.is_test:
            if self.WORKER_LEASE_DURATION_SECONDS < 1:
                raise ValueError("WORKER_LEASE_DURATION_SECONDS must be >= 1 in test")
            if self.TASK_PROGRESS_STALL_TIMEOUT_SECONDS < 1:
                raise ValueError("TASK_PROGRESS_STALL_TIMEOUT_SECONDS must be >= 1 in test")
            if self.TASK_WATCHDOG_SCAN_INTERVAL_SECONDS < 1:
                raise ValueError("TASK_WATCHDOG_SCAN_INTERVAL_SECONDS must be >= 1 in test")
        return self

    @field_validator("ANTIGRAVITY_EFFORT")
    @classmethod
    def validate_antigravity_effort(cls, v: str) -> str:
        v = v.lower()
        if v not in {"low", "medium", "high"}:
            raise ValueError("ANTIGRAVITY_EFFORT must be 'low', 'medium', or 'high'")
        return v

    ANTIGRAVITY_CLI_BIN: Path = Path(
        os.getenv("ANTIGRAVITY_CLI_BIN", str(Path.home() / ".local" / "bin" / "agy"))
    )
    ANTIGRAVITY_SDLC_SKILL_PATH: Path = Path(
        os.getenv(
            "ANTIGRAVITY_SDLC_SKILL_PATH",
            str(
                Path.home() / ".gemini" / "antigravity" / "skills" / "multi-agent-sdlc" / "SKILL.md"
            ),
        )
    )
    ANTIGRAVITY_TASK_TIMEOUT_SECONDS: int = int(
        os.getenv("ANTIGRAVITY_TASK_TIMEOUT_SECONDS", "1200")
    )
    WORKER_LEASE_DURATION_SECONDS: int = int(os.getenv("WORKER_LEASE_DURATION_SECONDS", "1800"))
    # Optional existing conversation for AlphaBrain's own repository only.
    # Client projects always receive their own project-bound conversation record.
    ALPHA_BRAIN_ANTIGRAVITY_CONVERSATION_ID: str = os.getenv(
        "ALPHA_BRAIN_ANTIGRAVITY_CONVERSATION_ID", ""
    )
    WORKTREE_BASE_DIR: Path = Path(
        os.getenv(
            "WORKTREE_BASE_DIR",
            str(Path.home() / "Library" / "Application Support" / "AlphaBrain" / "worktrees"),
        )
    )
    ATTACHED_DEVICE_ID: str = os.getenv("ATTACHED_DEVICE_ID", "local-mac-worker")
    WORKER_CONTROL_PLANE_URL: str = os.getenv("WORKER_CONTROL_PLANE_URL", "")
    WORKER_ID: str = os.getenv("WORKER_ID", "mac_worker_local")
    WORKER_STATE_DIR: Path = Path(
        os.getenv(
            "WORKER_STATE_DIR",
            str(Path.home() / "Library" / "Application Support" / "AlphaBrain" / "worker-state"),
        )
    )
    WORKER_SPOOL_FERNET_KEY: str = os.getenv("WORKER_SPOOL_FERNET_KEY", "")
    WORKER_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("WORKER_HTTP_TIMEOUT_SECONDS", "15"))
    WORKER_HEARTBEAT_SECONDS: int = int(os.getenv("WORKER_HEARTBEAT_SECONDS", "60"))
    TASK_PROGRESS_STALL_TIMEOUT_SECONDS: int = int(
        os.getenv("TASK_PROGRESS_STALL_TIMEOUT_SECONDS", "300")
    )
    TASK_WATCHDOG_SCAN_INTERVAL_SECONDS: int = int(
        os.getenv("TASK_WATCHDOG_SCAN_INTERVAL_SECONDS", "60")
    )
    WORKER_ALLOW_LOCAL_DB: bool = (
        os.getenv(
            "WORKER_ALLOW_LOCAL_DB",
            "true" if os.getenv("ENV", "development") != "production" else "false",
        ).lower()
        == "true"
    )
    WORKER_KEYCHAIN_SERVICE: str = os.getenv("WORKER_KEYCHAIN_SERVICE", "com.deploymate.alphabrain")
    WORKER_USE_KEYCHAIN: bool = os.getenv("WORKER_USE_KEYCHAIN", "false").lower() == "true"
    WORKTREE_MAX_DISK_GB: float = float(os.getenv("WORKTREE_MAX_DISK_GB", "100"))
    WORKTREE_MIN_FREE_GB: float = float(os.getenv("WORKTREE_MIN_FREE_GB", "20"))
    ALLOWED_REPO_ROOTS: tuple[Path, ...] = tuple(
        Path(item).expanduser()
        for item in _csv_env(
            "ALLOWED_REPO_ROOTS",
            "/Users/ajaytiwari/Desktop/Projects",
        )
    )
    ALLOWED_GATE_EXECUTABLES: tuple[str, ...] = _csv_env(
        "ALLOWED_GATE_EXECUTABLES",
        "pytest,ruff,mypy,node,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go",
    )
    # LiveKit (Local or Cloud WebRTC)

    # Live Translation
    TRANSLATE_MODEL: str = os.getenv("TRANSLATE_MODEL", "gemini-3.5-live-translate-preview")
    TRANSLATE_ENABLED: bool = os.getenv("TRANSLATE_ENABLED", "true").lower() == "true"
    DEFAULT_FOUNDER_LANGUAGE: str = os.getenv("DEFAULT_FOUNDER_LANGUAGE", "hi")

    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")


settings = Settings()
