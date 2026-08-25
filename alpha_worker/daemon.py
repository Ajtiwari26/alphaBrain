import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.connection import get_session_factory
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AgentType,
    TaskResult,
    TaskStatus,
    WorkerHealth,
)

from .adapters.antigravity import AntigravityAdapter
from .health import HardwareHealthChecker
from .worktree import WorktreeManager

logger = logging.getLogger("alpha_worker")


class AlphaWorkerDaemon:
    """Outbound-only macOS execution worker daemon."""

    def __init__(self, worker_id: str = "mac_worker_local"):
        self.worker_id = worker_id
        self.worktree_mgr = WorktreeManager()
        self.health_checker = HardwareHealthChecker()
        self.antigravity_adapter = AntigravityAdapter()
        self.running = False

    def select_adapter(self, agent_type: AgentType):
        if agent_type != AgentType.ANTIGRAVITY:
            raise ValueError(f"Unsupported execution agent: {agent_type.value}")
        return self.antigravity_adapter

    async def execute_task_cycle(self, session: AsyncSession) -> bool:
        """Runs a single polling and execution cycle. Returns True if a task was processed."""
        # 1. Health & Power Check
        health, _metrics = self.health_checker.evaluate_worker_health()
        if health == WorkerHealth.DRAINING:
            logger.warning(
                "Worker health is DRAINING (low battery / thermal). Pausing task intake."
            )
            return False

        # 2. Lease next task
        leased_tuple = await TaskEngine.lease_next_task(session, self.worker_id)
        if not leased_tuple:
            return False

        task_record, envelope = leased_tuple
        lease_token = task_record.lease_token
        logger.info(f"Leased task {envelope.task_id}: '{envelope.objective}'")

        worktree_path = None
        try:
            # 3. Create isolated worktree
            worktree_path = self.worktree_mgr.create_worktree(
                repo_path=envelope.repo,
                task_id=envelope.task_id,
                base_commit=envelope.base_commit,
            )

            # 4. Dispatch to adapter
            adapter = self.select_adapter(envelope.preferred_agent)
            result: TaskResult = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )

            # 5. Submit result and gate evidence back to master state engine
            await TaskEngine.submit_result(session, result, lease_token)
            logger.info(f"Completed task {envelope.task_id} with status {result.status.value}")

        except Exception as e:
            logger.error(f"Error executing task {envelope.task_id}: {e!s}", exc_info=True)
            failed_result = TaskResult(
                attempt_id=f"att_{envelope.task_id}_err",
                task_id=envelope.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=envelope.preferred_agent,
                model="unknown",
                base_commit=envelope.base_commit,
                blockers=[str(e)],
            )
            await TaskEngine.submit_result(session, failed_result, lease_token)
        finally:
            # 6. Safely clean up worktree
            if worktree_path and not (
                envelope.retain_worktree_for_preview and result.status == TaskStatus.COMPLETED
            ):
                try:
                    self.worktree_mgr.remove_worktree(envelope.repo, envelope.task_id)
                except Exception:
                    pass

        return True

    async def run_loop(self, poll_interval_seconds: int = 5):
        """Continuous background execution loop."""
        self.running = True
        session_factory = get_session_factory()

        logger.info(f"Starting AlphaWorkerDaemon [{self.worker_id}]")
        while self.running:
            try:
                async with session_factory() as session:
                    processed = await self.execute_task_cycle(session)
                    await session.commit()

                if not processed:
                    await asyncio.sleep(poll_interval_seconds)
            except Exception as e:
                logger.error(f"Worker loop exception: {e!s}")
                await asyncio.sleep(poll_interval_seconds)
