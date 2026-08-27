import re

with open("alpha_worker/daemon.py", "r") as f:
    content = f.read()

# Add PreviewSupervisor import
if "from alpha_worker.preview import PreviewSupervisor" not in content:
    content = "from alpha_worker.preview import PreviewSupervisor\n" + content

# Add preview_supervisor initialization
if "self.preview_supervisor =" not in content:
    content = content.replace("self.running = False", "self.running = False\n        self.preview_supervisor = PreviewSupervisor()")

# Add start_preview to execute_task_cycle
old_execute = """            # 4. Dispatch to adapter
            adapter = self.select_adapter(envelope.preferred_agent)
            result = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )

            await TaskEngine.submit_result(session, result, lease_token)"""
new_execute = """            # 4. Dispatch to adapter
            adapter = self.select_adapter(envelope.preferred_agent)
            result = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )

            if (
                result
                and result.status == TaskStatus.VERIFIED
                and getattr(envelope, "retain_worktree_for_preview", False)
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
                    if not result.blockers:
                        result.blockers = []
                    result.blockers.append(f"Preview startup failed: {e}")

            await TaskEngine.submit_result(session, result, lease_token)"""
content = content.replace(old_execute, new_execute)

with open("alpha_worker/daemon.py", "w") as f:
    f.write(content)
