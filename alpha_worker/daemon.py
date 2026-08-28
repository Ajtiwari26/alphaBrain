import asyncio
import json
import logging
import platform
import shutil
import socket
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.config import settings
from alpha_core.db.connection import get_session_factory
from alpha_core.policy.action_broker import (
    ActionBroker,
    ActionDecision,
    ActionRequest,
    ActionType,
)
from alpha_core.policy.action_broker import (
    action_broker as default_action_broker,
)
from alpha_core.security import redact_secrets, worker_kill_switch
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AgentType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    WorkerHealth,
    WorkerHealthReport,
    WorkerRegistration,
)

from .adapters.antigravity import AntigravityAdapter
from .adapters.antigravity_live import (
    AGYAttemptStatus,
    AntigravityAttemptOutcome,
)
from .control_plane import (
    ControlPlaneClient,
    ControlPlaneProtocolError,
    ControlPlaneUnavailable,
    DurableEventSpool,
    LeasedTask,
)
from .credentials import MacOSKeychain
from .health import HardwareHealthChecker
from .node_status import write_node_status
from .runtime_control import WorkerControlStore
from .worktree import WorktreeManager

logger = logging.getLogger("alpha_worker")


@dataclass(frozen=True)
class DaemonExecutionDecision:
    """Outcome of daemon pre-execution policy check and post-execution state mapping."""

    should_execute: bool
    next_task_status: TaskStatus
    reason: str
    action_decision: ActionDecision | None = None
    attempt_outcome: AntigravityAttemptOutcome | None = None
    gate_evidence_valid: bool = False


def evaluate_daemon_task_lifecycle(
    task: TaskEnvelope,
    *,
    action_broker: ActionBroker | None = None,
    human_approval_granted: bool = False,
    approver: str | None = None,
    attempt_outcome: AntigravityAttemptOutcome | None = None,
    has_valid_gate_evidence: bool = False,
) -> DaemonExecutionDecision:
    """
    Pure deterministic daemon decision function mapping an approved/leased task,
    ActionBroker policy check, and AGY attempt outcome to the safe next TaskStatus.

    Rules:
    1. Pre-execution ActionBroker check:
       - If action requires human approval and approval is not granted -> TaskStatus.WAITING_APPROVAL
         or TaskStatus.BLOCKED, should_execute=False.
       - If action is denied by broker -> TaskStatus.BLOCKED, should_execute=False.
    2. If attempt_outcome is None (pre-execution check passed):
       - should_execute=True, next_task_status=TaskStatus.RUNNING.
    3. Post-execution attempt outcome mapping:
       - If outcome status is CANCELLED -> TaskStatus.CANCELLED.
       - If outcome status is BLOCKED -> TaskStatus.BLOCKED.
       - If outcome status is TIMED_OUT, RATE_LIMITED, or FAILED -> TaskStatus.RETRYABLE_FAILED.
       - If outcome status is SUCCEEDED:
         - If gate evidence is missing or invalid -> TaskStatus.RETRYABLE_FAILED (never VERIFIED).
         - If all gate evidence is valid -> TaskStatus.VERIFIED (ready for verification gate, never auto-completed/accepted).
    """
    broker = action_broker or default_action_broker

    # 1. Envelope requires_approval check
    if task.requires_approval and not human_approval_granted:
        return DaemonExecutionDecision(
            should_execute=False,
            next_task_status=TaskStatus.WAITING_APPROVAL,
            reason="ActionBroker blocked execution: Task requires explicit human approval before execution",
            action_decision=ActionDecision(
                allowed=False,
                requires_human_approval=True,
                reason="Task requires explicit human approval before execution",
                action_type=ActionType.SHELL_EXEC,
            ),
            attempt_outcome=None,
            gate_evidence_valid=False,
        )

    # 2. Pre-execution ActionBroker check
    action_request = ActionRequest(
        action_type=ActionType.SHELL_EXEC,
        target=task.repo,
        command_or_params={
            "command": task.objective,
            "objective": task.objective,
            "allowed_paths": task.allowed_paths,
        },
        actor=f"worker:{task.preferred_agent.value}",
        risk_class=task.risk_class,
    )
    decision = broker.evaluate_action(
        action_request,
        human_approval_granted=human_approval_granted,
        approver=approver,
    )

    if not decision.allowed:
        target_status = (
            TaskStatus.WAITING_APPROVAL if decision.requires_human_approval else TaskStatus.BLOCKED
        )
        return DaemonExecutionDecision(
            should_execute=False,
            next_task_status=target_status,
            reason=f"ActionBroker blocked execution: {decision.reason}",
            action_decision=decision,
            attempt_outcome=None,
            gate_evidence_valid=False,
        )

    # If no attempt outcome provided yet, execution is permitted
    if attempt_outcome is None:
        return DaemonExecutionDecision(
            should_execute=True,
            next_task_status=TaskStatus.RUNNING,
            reason="Pre-execution policy checks passed; execution permitted",
            action_decision=decision,
            attempt_outcome=None,
            gate_evidence_valid=False,
        )

    # 2. Post-execution outcome evaluation
    if attempt_outcome.status == AGYAttemptStatus.CANCELLED:
        return DaemonExecutionDecision(
            should_execute=False,
            next_task_status=TaskStatus.CANCELLED,
            reason=attempt_outcome.blocked_reason or "Task cancelled during execution",
            action_decision=decision,
            attempt_outcome=attempt_outcome,
            gate_evidence_valid=False,
        )

    if attempt_outcome.status == AGYAttemptStatus.BLOCKED:
        return DaemonExecutionDecision(
            should_execute=False,
            next_task_status=TaskStatus.BLOCKED,
            reason=attempt_outcome.blocked_reason or "Task blocked by execution agent",
            action_decision=decision,
            attempt_outcome=attempt_outcome,
            gate_evidence_valid=False,
        )

    if attempt_outcome.status in {
        AGYAttemptStatus.FAILED,
        AGYAttemptStatus.TIMED_OUT,
        AGYAttemptStatus.RATE_LIMITED,
    }:
        return DaemonExecutionDecision(
            should_execute=False,
            next_task_status=TaskStatus.RETRYABLE_FAILED,
            reason=attempt_outcome.blocked_reason
            or f"Task failed with status {attempt_outcome.status.value}",
            action_decision=decision,
            attempt_outcome=attempt_outcome,
            gate_evidence_valid=False,
        )

    if attempt_outcome.status == AGYAttemptStatus.SUCCEEDED:
        # Must verify gate evidence
        has_evidence = has_valid_gate_evidence or bool(
            attempt_outcome.gate_evidence and attempt_outcome.qa_evidence
        )
        if not has_evidence:
            return DaemonExecutionDecision(
                should_execute=False,
                next_task_status=TaskStatus.RETRYABLE_FAILED,
                reason="Attempt succeeded but required gate evidence is missing or invalid",
                action_decision=decision,
                attempt_outcome=attempt_outcome,
                gate_evidence_valid=False,
            )

        # Succeeded with verified gate evidence maps strictly to VERIFIED (verifying state, never auto-completed/accepted)
        return DaemonExecutionDecision(
            should_execute=False,
            next_task_status=TaskStatus.VERIFIED,
            reason="Task execution succeeded with valid gate evidence; ready for verification gate",
            action_decision=decision,
            attempt_outcome=attempt_outcome,
            gate_evidence_valid=True,
        )

    # Fallback default
    return DaemonExecutionDecision(
        should_execute=False,
        next_task_status=TaskStatus.BLOCKED,
        reason=f"Unknown attempt status: {attempt_outcome.status}",
        action_decision=decision,
        attempt_outcome=attempt_outcome,
        gate_evidence_valid=False,
    )


class AlphaWorkerDaemon:
    """Outbound-only macOS execution worker daemon."""

    def __init__(
        self,
        worker_id: str | None = None,
        control_plane: ControlPlaneClient | None = None,
        spool: DurableEventSpool | None = None,
        control_store: WorkerControlStore | None = None,
    ):
        self.worker_id = worker_id or settings.WORKER_ID
        self.worktree_mgr = WorktreeManager()
        self.health_checker = HardwareHealthChecker()
        self.antigravity_adapter = AntigravityAdapter()
        from .preview import PreviewSupervisor

        self.preview_supervisor = PreviewSupervisor()
        self.control_plane = control_plane
        self.spool = spool
        self.control_store = control_store or WorkerControlStore(settings.WORKER_STATE_DIR)
        self.node_status_path = settings.WORKER_STATE_DIR / "status.json"
        if self.control_plane is None and settings.WORKER_CONTROL_PLANE_URL:
            if settings.ENV == "production" and not settings.WORKER_USE_KEYCHAIN:
                raise RuntimeError("Production worker requires WORKER_USE_KEYCHAIN=true")
            worker_token = settings.ALPHA_WORKER_TOKEN
            spool_key = settings.WORKER_SPOOL_FERNET_KEY
            if settings.WORKER_USE_KEYCHAIN:
                keychain = MacOSKeychain(settings.WORKER_KEYCHAIN_SERVICE)
                worker_token = keychain.get("worker-token")
                spool_key = keychain.get("worker-spool-fernet-key")
            self.control_plane = ControlPlaneClient(
                settings.WORKER_CONTROL_PLANE_URL,
                self.worker_id,
                worker_token,
                settings.WORKER_HTTP_TIMEOUT_SECONDS,
            )
            if self.spool is None:
                self.spool = DurableEventSpool(settings.WORKER_STATE_DIR / "spool", spool_key)
        if self.control_plane and self.spool is None:
            self.spool = DurableEventSpool(
                settings.WORKER_STATE_DIR / "spool", settings.WORKER_SPOOL_FERNET_KEY
            )
        self.running = False

    def _is_eligible_for_preview(self, envelope: TaskEnvelope, result: TaskResult) -> bool:
        if not envelope.retain_worktree_for_preview:
            return False
        if result.status == TaskStatus.VERIFIED:
            return True
        if result.status == TaskStatus.COMPLETED:
            return bool(result.gate_result and result.gate_result.all_passed)
        return False

    def select_adapter(self, agent_type: AgentType):
        if agent_type == AgentType.ANTIGRAVITY:
            return self.antigravity_adapter
        from alpha_worker.adapters.base import UnsupportedAdapter

        return UnsupportedAdapter(agent_type)

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
        leased_tuple = await TaskEngine.lease_next_task(
            session, self.worker_id, lease_duration_seconds=settings.WORKER_LEASE_DURATION_SECONDS
        )
        if not leased_tuple:
            return False

        try:
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to commit lease: {e}")
            await session.rollback()
            return False

        task_record, envelope = leased_tuple
        lease_token = task_record.lease_token
        logger.info(f"Leased task {envelope.task_id}: '{envelope.objective}'")

        worktree_path = None
        result: TaskResult | None = None
        result_committed = False
        try:
            # 3. Create isolated worktree (or resume if a prior attempt left one)
            worktree_path = self.worktree_mgr.create_or_resume_worktree(
                repo_path=envelope.repo,
                task_id=envelope.task_id,
                base_commit=envelope.base_commit,
            )

            # 4. Dispatch to adapter
            adapter = self.select_adapter(envelope.preferred_agent)
            result = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )

            if result and self._is_eligible_for_preview(envelope, result) and worktree_path:
                try:
                    preview_meta = self.preview_supervisor.start_preview(
                        worktree_path=worktree_path,
                        task_id=envelope.task_id,
                        project_id=envelope.project_id,
                    )
                    result.preview_evidence = preview_meta.to_dict()
                except Exception as e:
                    logger.error(f"Failed to start preview for {envelope.task_id}: {e}")
                    result.status = TaskStatus.RETRYABLE_FAILED
                    result.blockers.append(f"Preview startup failed: {e}")

            # 5. Submit result and gate evidence back to master state engine

            success = await TaskEngine.submit_result(session, result, lease_token, self.worker_id)
            if not success:
                logger.error(
                    f"Failed to persistently submit result for task {envelope.task_id} (lease expired or rejected)"
                )
                await session.rollback()
                return False

            try:
                await session.commit()
                result_committed = True
            except Exception as e:
                logger.error(f"Commit failed for task result: {e}")
                await session.rollback()
                return False

            logger.info(f"Completed task {envelope.task_id} with status {result.status.value}")

        except Exception as e:
            logger.error(f"Error executing task {envelope.task_id}: {e!s}", exc_info=True)
            from alpha_protocol import compute_packet_digest

            packet_sha256 = (
                compute_packet_digest(envelope)
                if getattr(envelope, "require_packet_binding", False)
                else None
            )
            import uuid

            failed_result = TaskResult(
                attempt_id=f"att_{envelope.task_id}_err_{uuid.uuid4().hex[:8]}",
                task_id=envelope.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=envelope.preferred_agent,
                model="unknown",
                base_commit=envelope.base_commit,
                packet_sha256=packet_sha256,
                blockers=[str(e)],
            )
            fail_success = await TaskEngine.submit_result(
                session, failed_result, lease_token, self.worker_id
            )
            if not fail_success:
                logger.error(
                    f"Failed to persistently submit error result for task {envelope.task_id} (lease expired or rejected)"
                )
                await session.rollback()
                return False

            try:
                await session.commit()
                result_committed = True
            except Exception as e:
                logger.error(f"Commit failed for error result: {e}")
                await session.rollback()
                return False
        finally:
            # 6. Safely clean up worktree
            retain_preview = bool(result and self._is_eligible_for_preview(envelope, result))
            if worktree_path and not retain_preview and result_committed:
                try:
                    self.worktree_mgr.remove_worktree(envelope.repo, envelope.task_id)
                except Exception:
                    pass

        return True

    def build_health_report(self, active_task_count: int = 0) -> WorkerHealthReport:
        health, metrics = self.health_checker.evaluate_worker_health()
        disk_free_gb = shutil.disk_usage(Path(settings.WORKTREE_BASE_DIR)).free / (1024**3)
        return WorkerHealthReport(
            worker_id=self.worker_id,
            status=health,
            battery_percent=int(metrics["battery_percentage"]),
            ac_power=bool(metrics["is_ac_power"]),
            thermal_pressure=str(metrics["thermal_state"]),
            disk_free_gb=disk_free_gb,
            active_task_count=active_task_count,
        )

    def build_registration(self) -> WorkerRegistration:
        return WorkerRegistration(
            worker_id=self.worker_id,
            hostname=socket.gethostname(),
            platform=f"{platform.system().lower()}-{platform.machine().lower()}",
        )

    async def execute_remote_cycle(self) -> bool:
        """Run one remote-control-plane task cycle without opening local DB sessions."""
        if not self.control_plane or not self.spool:
            raise RuntimeError("Remote worker mode is not configured")
        if self.control_store.read().paused:
            logger.warning("Worker local pause switch blocks task intake")
            return False
        health = self.build_health_report()
        write_node_status(self.node_status_path, health, paused=False)
        await self._sync_remote_presence(health)
        if health.should_drain:
            logger.warning("Worker is draining; remote task intake paused")
            return False

        lease = await self.control_plane.lease_next(self.worker_id, AgentType.ANTIGRAVITY.value)
        if not lease:
            return False
        if not worker_kill_switch.can_execute(lease.task.project_id):
            logger.warning("Worker kill switch blocked task %s", lease.task.task_id)
            return False
        return await self._execute_remote_lease(lease)

    async def _sync_remote_presence(self, health: WorkerHealthReport) -> None:
        """Register, replay confirmed-safe events, then report current health."""
        assert self.control_plane and self.spool
        try:
            await self.control_plane.register(self.build_registration())
            await self.spool.replay(self._deliver_spooled_event)
            await self.control_plane.report_health(health)
        except ControlPlaneUnavailable:
            self.spool.enqueue("health", health.model_dump(mode="json"), coalesce=True)
            raise

    async def _deliver_spooled_event(self, event_type: str, payload: dict[str, object]) -> None:
        assert self.control_plane
        if event_type == "health":
            await self.control_plane.report_health(WorkerHealthReport.model_validate(payload))
            return
        if event_type == "result":
            lease_token = payload.get("lease_token")
            result_payload = payload.get("result")
            if not isinstance(lease_token, str) or not isinstance(result_payload, dict):
                raise ValueError("Invalid spooled result event")
            await self.control_plane.submit_result(
                TaskResult.model_validate(result_payload), lease_token
            )
            return
        raise ValueError(f"Unsupported spooled event: {event_type}")

    async def _execute_remote_lease(self, lease: LeasedTask) -> bool:
        assert self.control_plane and self.spool
        envelope = lease.task
        worktree_path: Path | None = None
        result: TaskResult | None = None
        heartbeat_task: asyncio.Task[None] | None = None
        execution_task: asyncio.Task[TaskResult] | None = None
        cancel_requested = asyncio.Event()
        sleep_assertion: subprocess.Popen[bytes] | None = None
        try:
            worktree_path = self.worktree_mgr.create_or_resume_worktree(
                envelope.repo, envelope.task_id, envelope.base_commit
            )
            sleep_assertion = self._start_sleep_assertion()
            adapter = self.select_adapter(envelope.preferred_agent)
            execution_task = asyncio.create_task(
                adapter.execute(envelope, worktree_path, envelope.base_commit)
            )
            heartbeat_task = asyncio.create_task(
                self._remote_heartbeat_loop(
                    envelope.task_id,
                    lease.lease_token,
                    execution_task,
                    cancel_requested,
                )
            )
            result = await execution_task
        except asyncio.CancelledError:
            if not cancel_requested.is_set():
                raise
            logger.info("Remote cancellation stopped task %s", envelope.task_id)
            from alpha_protocol import compute_packet_digest

            packet_sha256 = (
                compute_packet_digest(envelope)
                if getattr(envelope, "require_packet_binding", False)
                else None
            )
            result = TaskResult(
                attempt_id=f"att_{envelope.task_id}_cancelled",
                task_id=envelope.task_id,
                status=TaskStatus.CANCELLED,
                agent=envelope.preferred_agent,
                model="cancelled-before-completion",
                base_commit=envelope.base_commit,
                packet_sha256=packet_sha256,
                blockers=["Founder cancelled active execution"],
            )
        except Exception as exc:
            logger.error("Remote task %s failed: %s", envelope.task_id, exc, exc_info=True)
            self._record_escalation(envelope.task_id, "execution_failed", str(exc))
            from alpha_protocol import compute_packet_digest

            packet_sha256 = (
                compute_packet_digest(envelope)
                if getattr(envelope, "require_packet_binding", False)
                else None
            )
            result = TaskResult(
                attempt_id=f"att_{envelope.task_id}_err",
                task_id=envelope.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=envelope.preferred_agent,
                model="unknown",
                base_commit=envelope.base_commit,
                packet_sha256=packet_sha256,
                blockers=[str(exc)],
            )
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
            self._stop_sleep_assertion(sleep_assertion)

        assert result
        if (
            not cancel_requested.is_set()
            and self._is_eligible_for_preview(envelope, result)
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
                logger.error(f"Failed to start preview for {envelope.task_id}: {e}")
                result.status = TaskStatus.RETRYABLE_FAILED
                result.blockers.append(f"Preview startup failed: {e}")

        if not cancel_requested.is_set():
            try:
                await self.control_plane.submit_result(result, lease.lease_token)
            except ControlPlaneUnavailable:
                self._record_escalation(
                    envelope.task_id, "result_delivery_deferred", "control plane unavailable"
                )
                self.spool.enqueue(
                    "result",
                    {"lease_token": lease.lease_token, "result": result.model_dump(mode="json")},
                )
                logger.warning(
                    "Spooling result for task %s until control plane returns", envelope.task_id
                )
        retain_preview = self._is_eligible_for_preview(envelope, result)
        if worktree_path and not retain_preview:
            try:
                self.worktree_mgr.remove_worktree(envelope.repo, envelope.task_id)
            except Exception:
                logger.exception("Worktree cleanup failed for %s", envelope.task_id)
        return True

    def _record_escalation(self, task_id: str, reason: str, detail: str) -> None:
        """Append founder-actionable failure record with atomic permission boundary."""
        path = settings.WORKER_STATE_DIR / "escalations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        safe_detail = redact_secrets(detail[:2000])
        with path.open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(
                    {
                        "task_id": task_id,
                        "reason": reason,
                        "detail": safe_detail,
                        "recorded_at": datetime.now(UTC).isoformat(),
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
        path.chmod(0o600)

    @staticmethod
    def _start_sleep_assertion() -> subprocess.Popen[bytes] | None:
        """Prevent idle sleep only while an eligible task is executing."""
        if platform.system() != "Darwin":
            return None
        return subprocess.Popen(
            ["caffeinate", "-dimsu"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    @staticmethod
    def _stop_sleep_assertion(process: subprocess.Popen[bytes] | None) -> None:
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    async def _remote_heartbeat_loop(
        self,
        task_id: str,
        lease_token: str,
        execution_task: asyncio.Task[TaskResult],
        cancel_requested: asyncio.Event,
    ) -> None:
        assert self.control_plane
        while True:
            await asyncio.sleep(settings.WORKER_HEARTBEAT_SECONDS)
            try:
                heartbeat_status = await self.control_plane.heartbeat(task_id, lease_token)
            except ControlPlaneProtocolError:
                logger.warning("Lease revoked for task %s; cancelling local execution", task_id)
                cancel_requested.set()
                execution_task.cancel()
                return
            if heartbeat_status == "cancel_requested":
                cancel_requested.set()
                execution_task.cancel()
                return

    async def _check_managed_previews(self, session: AsyncSession | None = None) -> None:
        """Worker heartbeat checks managed preview health."""
        if not self.preview_supervisor:
            return

        from .preview import PreviewStatus

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

    async def run_loop(self, poll_interval_seconds: int = 5):
        """Continuous background execution loop."""
        self.running = True
        if not self.control_plane and not settings.WORKER_ALLOW_LOCAL_DB:
            raise RuntimeError(
                "Production worker requires WORKER_CONTROL_PLANE_URL; local DB mode disabled"
            )
        session_factory = get_session_factory() if not self.control_plane else None

        logger.info(f"Starting AlphaWorkerDaemon [{self.worker_id}]")
        while self.running:
            try:
                if self.control_store.read().paused:
                    write_node_status(
                        self.node_status_path, self.build_health_report(), paused=True
                    )
                    await asyncio.sleep(poll_interval_seconds)
                    continue
                if self.control_plane:
                    await self._check_managed_previews()
                    processed = await self.execute_remote_cycle()
                    if not processed:
                        await asyncio.sleep(poll_interval_seconds)
                    continue
                assert session_factory is not None
                async with session_factory() as session:
                    await self._check_managed_previews(session)
                    # Reclaim crashed-worker leases before attempting new work.
                    await TaskEngine.timeout_expired_leases(session)
                    await TaskEngine.release_due_retries(session)
                    processed = await self.execute_task_cycle(session)
                    await session.commit()

                if not processed:
                    await asyncio.sleep(poll_interval_seconds)
            except Exception as e:
                logger.error(f"Worker loop exception: {e!s}")
                await asyncio.sleep(poll_interval_seconds)

        if self.control_plane:
            await self.control_plane.aclose()
