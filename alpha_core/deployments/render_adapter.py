
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import DeploymentAdapter


class RenderAdapter(DeploymentAdapter):
    def __init__(self, api_key: str, service_id: str):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = "https://api.render.com/v1"

        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def trigger_deployment(self, branch: str, commit_sha: str) -> str:
        url = f"{self.base_url}/services/{self.service_id}/deploys"
        payload = {"commitId": commit_sha, "branch": branch}
        response = self.session.post(url, headers=self._get_headers(), json=payload, timeout=30)
        response.raise_for_status()
        deploy_id = response.json().get("id")
        if not deploy_id:
            raise ValueError("Deployment ID missing in response")
        return deploy_id

    def poll_status(self, deployment_id: str) -> str:
        url = f"{self.base_url}/services/{self.service_id}/deploys/{deployment_id}"
        response = self.session.get(url, headers=self._get_headers(), timeout=30)
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
        response = self.session.get(url, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        service_data = response.json()
        domain = service_data.get("serviceDetails", {}).get("url")
        if not domain:
            return None
        return domain

    def rollback(self, deployment_id: str) -> str:
        # Fetch the target deployment to get its commit SHA
        url_get = f"{self.base_url}/services/{self.service_id}/deploys/{deployment_id}"
        response_get = self.session.get(url_get, headers=self._get_headers(), timeout=30)
        response_get.raise_for_status()
        deploy_data = response_get.json()

        # Depending on API response, commit info might be under "commit" object
        commit_obj = deploy_data.get("commit", {})
        commit_sha = commit_obj.get("id") or deploy_data.get("commitId")
        if not commit_sha:
            raise ValueError(f"Could not find commit SHA in Render deploy {deployment_id}")

        # Trigger a new deployment for that commit SHA
        url_post = f"{self.base_url}/services/{self.service_id}/deploys"
        payload = {"commitId": commit_sha}
        response_post = self.session.post(url_post, headers=self._get_headers(), json=payload, timeout=30)
        response_post.raise_for_status()
        deploy_id_new = response_post.json().get("id")
        if not deploy_id_new:
            raise ValueError("Rollback ID missing in response")
        return deploy_id_new
