import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="alphabrain-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_STATE_DIR / 'test.db'}"
os.environ["WORKTREE_BASE_DIR"] = str(TEST_STATE_DIR / "worktrees")
os.environ["MEMORY_GRAPH_PATH"] = str(TEST_STATE_DIR / "memory_graph")
os.environ["ALPHA_API_TOKEN"] = "test-api-token-with-at-least-32-characters"
os.environ["ALPHA_WORKER_TOKEN"] = "test-worker-token-with-at-least-32-characters"
os.environ["ALPHA_SIGNING_SECRET"] = "test-signing-secret-with-at-least-32-chars"
os.environ["PLIVO_AUTH_TOKEN"] = "test-plivo-auth-token"
os.environ["LIVEKIT_API_KEY"] = "test-livekit-key"
os.environ["LIVEKIT_API_SECRET"] = "test-livekit-secret-with-at-least-32-chars"
os.environ["PUBLIC_BASE_URL"] = "http://test"


import pytest_asyncio  # noqa: E402

from alpha_core.db.connection import get_engine  # noqa: E402
from alpha_core.db.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_state():
    yield
    shutil.rmtree(TEST_STATE_DIR, ignore_errors=True)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
def api_headers():
    return {"Authorization": f"Bearer {os.environ['ALPHA_API_TOKEN']}"}


@pytest.fixture
def worker_headers():
    return {"Authorization": f"Bearer {os.environ['ALPHA_WORKER_TOKEN']}"}
