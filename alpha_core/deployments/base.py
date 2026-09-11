import abc


class DeploymentAdapter(abc.ABC):
    @abc.abstractmethod
    def trigger_deployment(self, branch: str, commit_sha: str) -> str:
        """Triggers a deployment and returns a deployment_id."""
        pass

    @abc.abstractmethod
    def poll_status(self, deployment_id: str) -> str:
        """Returns the status of the deployment (e.g., 'READY', 'FAILED', 'BUILDING')."""
        pass

    @abc.abstractmethod
    def get_preview_url(self, deployment_id: str) -> str | None:
        """Returns the preview URL if available."""
        pass

    @abc.abstractmethod
    def rollback(self, deployment_id: str) -> str:
        """Triggers a rollback to the specified deployment ID."""
        pass
