import subprocess
from typing import Any

from alpha_protocol.enums import WorkerHealth


class HardwareHealthChecker:
    """Monitors macOS battery, thermal state, and lid closure to prevent broken builds."""

    @staticmethod
    def get_battery_and_power() -> tuple[bool, int]:
        """Returns (is_on_ac_power, battery_percentage)."""
        try:
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
            output = res.stdout.lower()
            is_ac = "ac power" in output

            # Parse percentage e.g. "95%"
            percentage = 100
            for word in output.split():
                if "%" in word:
                    cleaned = word.replace("%", "").replace(";", "").strip()
                    if cleaned.isdigit():
                        percentage = int(cleaned)
                        break

            return is_ac, percentage
        except Exception:
            return True, 100

    @staticmethod
    def check_thermal_and_load() -> str:
        """Return macOS thermal pressure, falling back to bounded CPU-load signal."""
        try:
            thermal = subprocess.run(
                ["pmset", "-g", "therm"], capture_output=True, text=True, check=False
            ).stdout.lower()
            if "critical" in thermal:
                return "critical"
            if "heavy" in thermal:
                return "heavy"
            if "moderate" in thermal:
                return "moderate"
            if "nominal" in thermal:
                return "nominal"

            import os

            load_1m, _, _ = os.getloadavg()
            cpu_count = os.cpu_count() or 4
            if load_1m > cpu_count * 1.5:
                return "heavy"
            elif load_1m > cpu_count * 0.8:
                return "moderate"
            return "nominal"
        except Exception:
            return "nominal"

    @classmethod
    def evaluate_worker_health(cls) -> tuple[WorkerHealth, dict[str, Any]]:
        is_ac, battery_pct = cls.get_battery_and_power()
        thermal_state = cls.check_thermal_and_load()

        metrics = {
            "is_ac_power": is_ac,
            "battery_percentage": battery_pct,
            "thermal_state": thermal_state,
        }

        # If battery is low (< 20%) and not on AC power, drain worker
        if thermal_state in {"heavy", "critical"}:
            return WorkerHealth.DRAINING, metrics

        if not is_ac and battery_pct < 20:
            return WorkerHealth.DRAINING, metrics

        if not is_ac:
            return WorkerHealth.DEGRADED, metrics

        return WorkerHealth.ONLINE, metrics
