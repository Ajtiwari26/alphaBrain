
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import DeploymentAdapter


class VercelAdapter(DeploymentAdapter):
    def __init__(self, api_token: str, project_id: str, project_name: str, team_id: str | None = None):
        self.api_token = api_token
        self.project_id = project_id
        self.project_name = project_name
        self.team_id = team_id
        self.base_url = "https://api.vercel.com"

        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _get_params(self) -> dict[str, str]:
        params = {}
        if self.team_id:
            params["teamId"] = self.team_id
        return params

    def trigger_deployment(self, branch: str, commit_sha: str) -> str:
        url = f"{self.base_url}/v13/deployments"
        payload = {
            "name": self.project_name,
            "gitSource": {
                "type": "github",
                "ref": branch,
                "sha": commit_sha
            }
        }
        response = self.session.post(
            url, headers=self._get_headers(), params=self._get_params(), json=payload, timeout=30
        )
        response.raise_for_status()
        deploy_id = response.json().get("id")
        if not deploy_id:
            raise ValueError("Deployment ID missing in response")
        return deploy_id

    def poll_status(self, deployment_id: str) -> str:
        if deployment_id.startswith("vercel_job:"):
            target_id = deployment_id.split(":")[1]
            url = f"{self.base_url}/v9/projects/{self.project_id}/rollback/{target_id}"
            response = self.session.get(url, headers=self._get_headers(), params=self._get_params(), timeout=30)
            response.raise_for_status()
            status = response.json().get("jobStatus", "")
            if status == "succeeded":
                return "READY"
            elif status == "failed":
                return "FAILED"
            return "BUILDING"

        url = f"{self.base_url}/v13/deployments/{deployment_id}"
        response = self.session.get(url, headers=self._get_headers(), params=self._get_params(), timeout=30)
        response.raise_for_status()
        state = response.json().get("readyState", "")
        if state == "READY":
            return "READY"
        elif state == "ERROR":
            return "FAILED"
        return "BUILDING"

    def get_preview_url(self, deployment_id: str) -> str | None:
        url = f"{self.base_url}/v13/deployments/{deployment_id}"
        response = self.session.get(url, headers=self._get_headers(), params=self._get_params(), timeout=30)
        response.raise_for_status()
        domain = response.json().get("url")
        if domain:
            return f"https://{domain}"
        return None

    def rollback(self, deployment_id: str) -> str:
        url = f"{self.base_url}/v9/projects/{self.project_id}/rollback/{deployment_id}"
        response = self.session.post(url, headers=self._get_headers(), params=self._get_params(), timeout=30)
        response.raise_for_status()
        # Vercel creates a rollback job against the original deployment id
        # We encode it to let poll_status know it needs to poll the rollback API instead of normal deployment API
        return f"vercel_job:{deployment_id}"
