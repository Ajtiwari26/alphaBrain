"""
testscript/test_render_manifest.py
Validates Render Blueprint specification render.yaml for Alpha Brain Web Service.
"""

from pathlib import Path


def test_render_manifest_structure_and_constraints():
    manifest_path = Path(__file__).resolve().parent.parent / "render.yaml"
    assert manifest_path.exists(), "render.yaml must exist at project root"

    content = manifest_path.read_text(encoding="utf-8")

    # Essential Blueprint fields
    assert 'version: "1"' in content
    assert "services:" in content
    assert "type: web" in content
    assert "name: alpha-brain-staging" in content
    assert "runtime: python" in content
    assert "plan: free" in content
    assert "region: singapore" in content
    assert 'buildCommand: "pip install -r requirements.txt"' in content
    assert 'startCommand: "uvicorn alpha_core.api.app:app --host 0.0.0.0 --port $PORT"' in content
    assert "healthCheckPath: /health/ready" in content

    # Ensure zero Redis dependencies
    assert "redis" not in content.lower(), "render.yaml must not contain Redis service"

    # Ensure required non-secret env vars exist
    assert "key: ENV\n        value: staging" in content
    assert 'key: DEBUG\n        value: "false"' in content
    assert "key: GEMINI_USE_VERTEX" in content
    assert "key: GEMINI_LIVE_MODEL" in content
    assert "key: GEMINI_LIVE_VOICE" in content
    assert "key: ALLOWED_GATE_EXECUTABLES" in content
    assert 'key: WORKER_ALLOW_LOCAL_DB\n        value: "false"' in content
    assert 'key: ANTIGRAVITY_EXECUTION_ENABLED\n        value: "false"' in content

    # Ensure manual / secret configuration entries have sync: false
    assert "key: PUBLIC_BASE_URL\n        sync: false" in content
    assert "key: CORS_ORIGINS\n        sync: false" in content
    assert "key: DATABASE_URL\n        sync: false" in content
    assert "key: ALPHA_API_TOKEN\n        sync: false" in content
    assert "key: ALPHA_WORKER_TOKEN\n        sync: false" in content
    assert "key: ALPHA_SIGNING_SECRET\n        sync: false" in content
    assert "key: GEMINI_API_KEY\n        sync: false" in content
    assert "key: LIVEKIT_URL\n        sync: false" in content
    assert "key: LIVEKIT_API_KEY\n        sync: false" in content
    assert "key: LIVEKIT_API_SECRET\n        sync: false" in content
