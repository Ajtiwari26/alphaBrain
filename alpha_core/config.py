import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.local")
load_dotenv(PROJECT_ROOT / ".env")
USE_VERTEX = os.getenv("GEMINI_USE_VERTEX", "false").lower() == "true"


def _csv_env(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


class Settings(BaseModel):
    # App Information
    APP_NAME: str = "Alpha Brain"
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

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
            else "gemini-2.5-flash-native-audio-preview-12-2025"
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
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///" + str(Path(__file__).resolve().parent.parent / "alpha_brain.db"),
    )

    # Local Temporal Orchestrator
    TEMPORAL_HOST: str = os.getenv("TEMPORAL_HOST", "localhost:7233")
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")

    # Local Paths & Hardware
    WORKSPACE_ROOT: Path = PROJECT_ROOT
    MEMORY_GRAPH_PATH: Path = Path(os.getenv("MEMORY_GRAPH_PATH", "/Users/ajaytiwari/Desktop/Projects/memory_graph"))
    WORKTREE_BASE_DIR: Path = Path(
        os.getenv(
            "WORKTREE_BASE_DIR",
            str(Path.home() / "Library" / "Application Support" / "AlphaBrain" / "worktrees"),
        )
    )
    ATTACHED_DEVICE_ID: str = os.getenv("ATTACHED_DEVICE_ID", "local-mac-worker")
    ALLOWED_REPO_ROOTS: tuple[Path, ...] = tuple(
        Path(item).expanduser() for item in _csv_env(
            "ALLOWED_REPO_ROOTS",
            "/Users/ajaytiwari/Desktop/Projects",
        )
    )
    ALLOWED_GATE_EXECUTABLES: tuple[str, ...] = _csv_env(
        "ALLOWED_GATE_EXECUTABLES",
        "pytest,ruff,mypy,npm,npx,pnpm,yarn,swift,xcodebuild,cargo,go",
    )
    ALLOWED_CLAUDE_TOOLS: tuple[str, ...] = _csv_env(
        "ALLOWED_CLAUDE_TOOLS",
        "Read,Edit,Write",
    )

    # LiveKit (Local or Cloud WebRTC)
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")


settings = Settings()
