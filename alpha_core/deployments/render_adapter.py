
import requests

from .base import DeploymentAdapter


class RenderAdapter(DeploymentAdapter):
    def __init__(self, api_key: str, service_id: str):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = "https://api.render.com/v1"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def trigger_deployment(self, branch: str, commit_sha: str) -> str:
        url = f"{self.base_url}/services/{self.service_id}/deploys"
        # Render supports passing commitId to deploy a specific commit
        payload = {"commitId": commit_sha}
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        deploy_id = response.json().get("id")
        if not deploy_id:
            raise ValueError("Deployment ID missing in response")
        return deploy_id

    def poll_status(self, deployment_id: str) -> str:
        url = f"{self.base_url}/services/{self.service_id}/deploys/{deployment_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=10)
        response.raise_for_status()
        status = response.json().get("status", "")
        if status == "live":
            return "READY"
        elif status in ("build_failed", "update_failed", "canceled"):
            return "FAILED"
        return "BUILDING"

    def get_preview_url(self, deployment_id: str) -> str | None:
        # Render services do not natively expose unique preview URLs per deploy via standard GET service.
        # It typically returns the main service URL. Documenting this limitation explicitly.
        url = f"{self.base_url}/services/{self.service_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=10)
        response.raise_for_status()
        service_data = response.json()
        domain = service_data.get("serviceDetails", {}).get("url")
        if not domain:
            raise ValueError("Service URL missing in response")
        return domain

    def rollback(self, deployment_id: str) -> str:
        url = f"{self.base_url}/services/{self.service_id}/rollbacks"
        payload = {"deployId": deployment_id}
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        deploy_id_new = response.json().get("id")
        if not deploy_id_new:
            raise ValueError("Rollback ID missing in response")
        return deploy_id_new
