from .base import DeploymentAdapter


class RollbackPipeline:
    def __init__(self, adapter: DeploymentAdapter):
        self.adapter = adapter

    def execute_rollback(self, deployment_id: str) -> str:
        """Executes a rollback for the given deployment ID."""
        return self.adapter.rollback(deployment_id)
