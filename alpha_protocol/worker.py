"""
Alpha Protocol Worker Schemas v1
==================================
Worker registration, capability declaration, health reports,
and lease contracts for the Mac execution daemon.

Protocol version: 1
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .enums import PROTOCOL_VERSION, AgentType, WorkerHealth


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkerCapability(BaseModel):
    """Declares what a worker can execute."""
    supported_agents: list[AgentType] = Field(
        default_factory=lambda: [AgentType.ANTIGRAVITY],
    )
    supported_languages: list[str] = Field(
        default_factory=lambda: ["python", "javascript", "typescript", "swift"],
    )
    max_concurrent_tasks: int = Field(default=2, ge=1, le=10)
    has_gpu: bool = False
    has_display: bool = True
    platform: str = Field(default="macos-arm64")


class WorkerRegistration(BaseModel):
    """Worker announces itself to the control plane."""
    protocol_version: str = Field(default=PROTOCOL_VERSION)
    worker_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    hostname: str
    platform: str = Field(default="macos-arm64")
    capability: WorkerCapability = Field(default_factory=WorkerCapability)
    identity_token: str | None = Field(
        default=None, description="Signed short-lived worker identity token"
    )
    registered_at: datetime = Field(default_factory=utc_now)


class WorkerHealthReport(BaseModel):
    """Periodic health status from worker daemon."""
    worker_id: str
    status: WorkerHealth = WorkerHealth.ONLINE
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    ac_power: bool | None = None
    thermal_pressure: str | None = Field(
        default=None, description="nominal, moderate, heavy, critical"
    )
    cpu_load_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    disk_free_gb: float | None = Field(default=None, ge=0.0)
    active_task_count: int = Field(default=0, ge=0)
    uptime_seconds: int = Field(default=0, ge=0)
    reported_at: datetime = Field(default_factory=utc_now)

    @property
    def should_drain(self) -> bool:
        """Determine if worker should stop accepting new tasks."""
        if self.battery_percent is not None and not self.ac_power:
            if self.battery_percent < 20:
                return True
        if self.thermal_pressure in ("heavy", "critical"):
            return True
        return False
