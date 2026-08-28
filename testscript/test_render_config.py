from pathlib import Path

import yaml


def test_render_config():
    render_yaml_path = Path(__file__).parent.parent / "render.yaml"
    with open(render_yaml_path) as f:
        config = yaml.safe_load(f)

    web_service = next(
        (service for service in config.get("services", []) if service.get("type") == "web"), None
    )
    assert web_service is not None, "Web service not found in render.yaml"

    assert web_service.get("autoDeploy") is False, "autoDeploy must be false"
    assert web_service.get("healthCheckPath") == "/health/ready", (
        "healthCheckPath must be /health/ready"
    )
