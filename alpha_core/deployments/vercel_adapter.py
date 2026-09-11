
import requests

from .base import DeploymentAdapter


class VercelAdapter(DeploymentAdapter):
    def __init__(self, api_token: str, project_id: str, team_id: str | None = None):
        self.api_token = api_token
        self.project_id = project_id
        self.team_id = team_id
        self.base_url = "https://api.vercel.com"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _get_params(self) -> dict:
        params = {}
        if self.team_id:
            params["teamId"] = self.team_id
        return params

    def trigger_deployment(self, branch: str, commit_sha: str) -> str:
        url = f"{self.base_url}/v13/deployments"
        payload = {
            "name": self.project_id,
            "gitSource": {
                "type": "github",
                "ref": branch,
                "sha": commit_sha
            }
        }
        response = requests.post(
            url, headers=self._get_headers(), params=self._get_params(), json=payload
        )
        response.raise_for_status()
        return response.json().get("id", "")

    def poll_status(self, deployment_id: str) -> str:
        url = f"{self.base_url}/v13/deployments/{deployment_id}"
        response = requests.get(url, headers=self._get_headers(), params=self._get_params())
        response.raise_for_status()
        state = response.json().get("readyState", "")
        if state == "READY":
            return "READY"
        elif state == "ERROR":
            return "FAILED"
        return "BUILDING"

    def get_preview_url(self, deployment_id: str) -> str | None:
        url = f"{self.base_url}/v13/deployments/{deployment_id}"
        response = requests.get(url, headers=self._get_headers(), params=self._get_params())
        response.raise_for_status()
        domain = response.json().get("url")
        if domain:
            return f"https://{domain}"
        return None

    def rollback(self, deployment_id: str) -> str:
        url = f"{self.base_url}/v9/projects/{self.project_id}/rollback/{deployment_id}"
        response = requests.post(url, headers=self._get_headers(), params=self._get_params())
        response.raise_for_status()
        return response.json().get("id", deployment_id)
