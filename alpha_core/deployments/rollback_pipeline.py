import logging
import time

from .base import DeploymentAdapter

logger = logging.getLogger(__name__)

class RollbackFailedError(RuntimeError):
    """Exception raised when a rollback operation fails."""
    pass

class RollbackPipeline:
    def __init__(self, adapter: DeploymentAdapter):
        self.adapter = adapter

    def execute_rollback(self, deployment_id: str, timeout_seconds: int = 300, poll_interval: int = 10) -> str:
        """Executes a rollback and actively monitors the deployment health."""
        logger.info(f"Initiating rollback for deployment: {deployment_id}")
        try:
            tracking_id = self.adapter.rollback(deployment_id)
            logger.info(f"Rollback triggered. Tracking ID or status: {tracking_id}")

            start_time = time.time()

            # Generic polling loop for standard deployment IDs
            while (time.time() - start_time) < timeout_seconds:
                try:
                    status = self.adapter.poll_status(tracking_id)
                    logger.info(f"Rollback status: {status}")
                    if status == "READY":
                        logger.info("Rollback completed successfully.")
                        return tracking_id
                    elif status == "FAILED":
                        logger.error("Rollback failed during polling.")
                        raise RollbackFailedError("Rollback failed.")
                except RollbackFailedError:
                    raise
                except Exception as poll_e:
                    logger.warning(f"Failed to poll status for {tracking_id}: {poll_e}")
                    # Keep polling, the API might just be flaky

                time.sleep(poll_interval)

            raise TimeoutError(f"Rollback timed out after {timeout_seconds}s")

        except Exception as e:
            logger.error(f"Rollback pipeline orchestration failed: {e}")
            raise
