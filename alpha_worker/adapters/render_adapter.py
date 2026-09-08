import asyncio
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    url: str
    status: str
    health_ok: bool


class RenderAdapter:
    def __init__(self, api_key: str, service_id: str):
        if not api_key:
            raise ValueError("Render API key cannot be empty")
        if not service_id:
            raise ValueError("Render service ID cannot be empty")
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = "https://api.render.com/v1"

    def _mask_secrets(self, text: str) -> str:
        if not self.api_key:
            return text
        return text.replace(self.api_key, "***")

    def _make_request(
        self, method: str, endpoint: str, data: bytes | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
        )
        if data:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                response_data = response.read()
                if not response_data:
                    return {}
                return cast(dict[str, Any], json.loads(response_data.decode()))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            error_msg = self._mask_secrets(error_body)
            raise RuntimeError(f"Render API error {e.code}: {error_msg}") from e
        except Exception as e:
            error_msg = self._mask_secrets(str(e))
            raise RuntimeError(f"Render API request failed: {error_msg}") from e

    async def _get_service_url(self) -> str:
        data = await asyncio.to_thread(self._make_request, "GET", f"/services/{self.service_id}")
        service = data.get("service", data) if "service" in data else data
        service_url = service.get("url")
        if not service_url:
            raise RuntimeError("Could not determine service URL")
        return str(service_url)

    async def deploy_preview(
        self, worktree_path: Path | None = None, commit_id: str | None = None
    ) -> DeploymentResult:
        """Triggers a deployment via Render API with mandatory commit SHA and fail-closed environment check."""
        if not commit_id or not bool(re.match(r"^[0-9a-fA-F]{40}$", str(commit_id))):
            raise ValueError(
                f"Mandatory explicit 40-character commit SHA required, got: '{commit_id}'"
            )

        # Reject production targets and fail-closed on unknown environments in preview mode
        service_data = await asyncio.to_thread(
            self._make_request, "GET", f"/services/{self.service_id}"
        )
        service = (
            service_data.get("service", service_data) if "service" in service_data else service_data
        )
        service_env = service.get("env") or service.get("environment")
        if not service_env or str(service_env).lower() not in (
            "preview",
            "development",
            "staging",
            "test",
        ):
            raise RuntimeError(
                f"Target environment '{service_env}' invalid or production in preview mode"
            )

        payload = json.dumps({"commitId": commit_id}).encode("utf-8")

        data = await asyncio.to_thread(
            self._make_request, "POST", f"/services/{self.service_id}/deploys", data=payload
        )

        deploy_id = data.get("id")
        if not deploy_id:
            raise RuntimeError(
                f"Failed to extract deploy ID: {self._mask_secrets(json.dumps(data))}"
            )

        status = await self.poll_status(deploy_id)

        # Independently verify deployed revision
        if status == "LIVE":
            deploy_data = await asyncio.to_thread(
                self._make_request, "GET", f"/services/{self.service_id}/deploys/{deploy_id}"
            )
            deployed_commit = deploy_data.get("commit", {}).get("id") or deploy_data.get("commitId")
            if not deployed_commit or not str(deployed_commit).lower().startswith(
                commit_id.lower()
            ):
                raise RuntimeError(
                    f"Deployed revision mismatch: expected {commit_id}, got {deployed_commit}"
                )

        service_url = await self._get_service_url()

        health_ok = False
        if status == "LIVE":
            health_ok = await self.check_health(service_url)

        return DeploymentResult(url=service_url, status=status, health_ok=health_ok)

    async def poll_status(self, deploy_id: str, timeout_seconds: int = 300) -> str:
        """Polls the deployment status."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        while loop.time() - start_time < timeout_seconds:
            data = await asyncio.to_thread(
                self._make_request, "GET", f"/services/{self.service_id}/deploys/{deploy_id}"
            )

            status = data.get("status", "")

            if status in ("live", "deactivated"):
                return str(status).upper()
            if status in ("build_failed", "update_failed", "canceled"):
                return str(status).upper()

            await asyncio.sleep(5)

        return "TIMEOUT"

    async def check_health(self, url: str) -> bool:
        """Validates that the deployed URL is reachable and returns HTTP 200."""
        try:

            def fetch() -> bool:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as response:
                    return bool(response.getcode() == 200)

            res = await asyncio.to_thread(fetch)
            return bool(res)
        except Exception as e:
            logger.debug(f"Health check failed for {url}: {e}")
            return False
