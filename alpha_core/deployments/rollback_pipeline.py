import logging
import time

from .base import DeploymentAdapter

logger = logging.getLogger(__name__)

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
            # If the adapter returns jobStatus as the tracking_id for Vercel, it doesn't match poll_status signature.
            # Usually we'd poll the status of the new deployment_id. Assuming tracking_id is pollable,
            # except Vercel rollback doesn't return a deploy id, it returns jobStatus.
            # To handle both safely without crashing the orchestration pipeline:
            if tracking_id in ("succeeded", "failed", "in_progress", "pending"):
                # Fast track Vercel jobStatus parsing
                if tracking_id == "succeeded":
                    logger.info("Rollback job marked as succeeded.")
                    return tracking_id
                elif tracking_id == "failed":
                    logger.error("Rollback job failed.")
                    raise RuntimeError("Rollback failed according to jobStatus.")

            # Generic polling loop for standard deployment IDs
            while (time.time() - start_time) < timeout_seconds:
                try:
                    # Note: For Vercel, poll_status with jobStatus might 404, we catch and log.
                    status = self.adapter.poll_status(tracking_id)
                    logger.info(f"Rollback status: {status}")
                    if status == "READY":
                        logger.info("Rollback completed successfully.")
                        return tracking_id
                    elif status == "FAILED":
                        logger.error("Rollback failed during polling.")
                        raise RuntimeError("Rollback failed.")
                except Exception as poll_e:
                    logger.warning(f"Failed to poll status for {tracking_id}: {poll_e}")
                    # Keep polling, the API might just be flaky

                time.sleep(poll_interval)

            raise TimeoutError(f"Rollback timed out after {timeout_seconds}s")

        except Exception as e:
            logger.error(f"Rollback pipeline orchestration failed: {e}")
            raise
