import re

with open("alpha_worker/daemon.py", "r") as f:
    content = f.read()

# Add PreviewSupervisor import
if "from .preview import PreviewSupervisor" not in content:
    content = content.replace("from .node_status import write_node_status", "from .node_status import write_node_status\nfrom .preview import PreviewSupervisor")

# Add preview_supervisor initialization
if "self.preview_supervisor =" not in content:
    content = content.replace("self.node_status_path = settings.WORKER_STATE_DIR / \"node_status.json\"", "self.node_status_path = settings.WORKER_STATE_DIR / \"node_status.json\"\n        self.preview_supervisor = PreviewSupervisor()")

# Add start_preview to execute_task_cycle
old_execute = """            result = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )

            await TaskEngine.submit_result(session, result, lease_token)"""
new_execute = """            result = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )

            if (
                result
                and result.status == TaskStatus.VERIFIED
                and envelope.retain_worktree_for_preview
                and worktree_path
            ):
                try:
                    preview_meta = self.preview_supervisor.start_preview(
                        worktree_path=worktree_path,
                        task_id=envelope.task_id,
                        project_id=envelope.project_id,
                    )
                    result.preview_evidence = preview_meta.to_dict()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to start preview for {envelope.task_id}: {e}")
                    result.status = TaskStatus.RETRYABLE_FAILED
                    result.blockers.append(f"Preview startup failed: {e}")

            await TaskEngine.submit_result(session, result, lease_token)"""
content = content.replace(old_execute, new_execute)

# Add check_managed_previews
check_managed = """
    async def _check_managed_previews(self, session: AsyncSession | None = None) -> None:
        if not self.preview_supervisor:
            return

        from .preview import PreviewStatus
        import logging
        logger = logging.getLogger(__name__)

        for path in self.preview_supervisor._state_dir.glob("*.json"):
            task_id = path.stem
            metadata = self.preview_supervisor.load_persisted_metadata(task_id)
            if not metadata or metadata.status == PreviewStatus.STOPPED:
                continue

            is_healthy = self.preview_supervisor.check_health(metadata)
            if not is_healthy:
                logger.warning(
                    f"Preview for task {task_id} failed health check: {metadata.health_error}"
                )
                if metadata.restart_count < 3:
                    try:
                        self.preview_supervisor.restart_unhealthy_preview(metadata)
                    except Exception as e:
                        logger.error(f"Failed to restart preview for {task_id}: {e}")
                else:
                    self.preview_supervisor.terminate_preview(metadata)
                    reason = f"Preview exceeded max restarts ({metadata.restart_count}). Last error: {metadata.health_error}"
                    if session:
                        await TaskEngine.block_task(
                            session, task_id, reason=reason, actor="preview_supervisor"
                        )
                    elif self.control_plane:
                        self._record_escalation(task_id, "preview_crashed", reason)
"""
if "def _check_managed_previews" not in content:
    content = content.replace("    async def run_loop(self, poll_interval_seconds: int = 5):", check_managed + "\n    async def run_loop(self, poll_interval_seconds: int = 5):")

if "await self._check_managed_previews()" not in content:
    content = content.replace("processed = await self.execute_remote_cycle()", "await self._check_managed_previews()\n                    processed = await self.execute_remote_cycle()")
    content = content.replace("await TaskEngine.timeout_expired_leases(session)", "await self._check_managed_previews(session)\n                    await TaskEngine.timeout_expired_leases(session)")

with open("alpha_worker/daemon.py", "w") as f:
    f.write(content)
