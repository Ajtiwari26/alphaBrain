import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Hermetic test mock for LiveKit WebRTC dependencies
try:
    import livekit  # noqa: F401
except ImportError:
    from importlib.abc import Loader
    from importlib.machinery import ModuleSpec
    from unittest.mock import MagicMock

    class KwargsPreservingMock(MagicMock):
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            inst = MagicMock()
            for k, v in kwargs.items():
                setattr(inst, k, v)
            inst.with_identity.return_value = inst
            inst.with_name.return_value = inst
            inst.with_grants.return_value = inst
            inst.with_ttl.return_value = inst
            inst.to_jwt.return_value = "mock-livekit-jwt-token-string-sample-1234567890"
            return inst

    class LiveKitMockFinder:
        def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> ModuleSpec | None:
            if fullname.startswith("livekit"):
                class MockLoader(Loader):
                    def create_module(self, spec: ModuleSpec) -> Any:
                        m = KwargsPreservingMock()
                        m.__path__ = []
                        m.__name__ = fullname
                        return m

                    def exec_module(self, module: Any) -> None:
                        pass

                return ModuleSpec(fullname, MockLoader(), is_package=True)
            return None

    sys.meta_path.insert(0, LiveKitMockFinder())

TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="alphabrain-tests-"))
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_STATE_DIR / 'test.db'}"
os.environ["WORKTREE_BASE_DIR"] = str(TEST_STATE_DIR / "worktrees")
os.environ["MEMORY_GRAPH_PATH"] = str(TEST_STATE_DIR / "memory_graph")
os.environ["WORKER_STATE_DIR"] = str(TEST_STATE_DIR / "worker")
os.environ["WORKER_USE_KEYCHAIN"] = "false"
os.environ["WORKER_SPOOL_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["ALPHA_API_TOKEN"] = "test-api-token-with-at-least-32-characters"
os.environ["ALPHA_WORKER_TOKEN"] = "test-worker-token-with-at-least-32-characters"
os.environ["ALPHA_SIGNING_SECRET"] = "test-signing-secret-with-at-least-32-chars"
os.environ["ALPHA_SIGNING_SECRET_alpha_production_v1"] = os.environ["ALPHA_SIGNING_SECRET"]
os.environ["PLIVO_AUTH_TOKEN"] = "test-plivo-auth-token"
os.environ["LIVEKIT_API_KEY"] = "test-livekit-key"
os.environ["LIVEKIT_API_SECRET"] = "test-livekit-secret-with-at-least-32-chars"
os.environ["PUBLIC_BASE_URL"] = "http://test"


import pytest_asyncio  # noqa: E402

from alpha_core.db.connection import get_engine  # noqa: E402
from alpha_core.db.models import Base  # noqa: E402
from alpha_core.security import create_worker_identity_token  # noqa: E402


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
    return {
        "X-Alpha-Worker-Identity": create_worker_identity_token("alpha_worker"),
    }
