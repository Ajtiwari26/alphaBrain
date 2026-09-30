"""Inito Node Keeper - Mac hardware and system health monitor for autonomous execution.

Monitors battery level, AC power state, thermal pressure, clamshell/display state,
CPU load, and memory allocation to safeguard hardware during autonomous worker tasks.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class InitoNodeKeeper:
    """Monitors macOS / host system health and hardware telemetry for autonomous execution."""

    def __init__(
        self,
        sysfs_path: str | Path | None = None,
        usb_serial: str = "10BF5P2AZF0010T",
        usb_device_name: str = "iQOO 12 Flagship",
        min_battery_percent: float = 20.0,
    ) -> None:
        """Initialize the InitoNodeKeeper.

        Args:
            sysfs_path: Optional path to a sysfs root or simulated sysfs directory
                (used for testing or Linux environments).
            usb_serial: Target device serial number.
            usb_device_name: Target device name for UI display.
            min_battery_percent: Minimum battery threshold required when on battery power.
        """
        self.sysfs_path = Path(sysfs_path) if sysfs_path else None
        self.usb_serial = usb_serial
        self.usb_device_name = usb_device_name
        self.min_battery_percent = min_battery_percent

    # -------------------------------------------------------------------------
    # Battery & AC Power Detection
    # -------------------------------------------------------------------------

    def get_battery_state(self) -> dict[str, Any]:
        """Query battery level, AC power connection, and charging state.

        Checks simulated sysfs if provided, falls back to `pmset -g batt` on macOS,
        then `psutil.sensors_battery()`, and finally safe defaults.

        Returns:
            Dict containing:
                - battery_level_percent (float)
                - is_on_ac (bool)
                - charging (bool)
        """
        # 1. Simulated sysfs or Linux /sys/class/power_supply
        if self.sysfs_path and self.sysfs_path.exists():
            sysfs_result = self._read_sysfs_battery()
            if sysfs_result is not None:
                return sysfs_result

        # 2. macOS pmset -g batt
        if shutil.which("pmset"):
            pmset_result = self._read_pmset_battery()
            if pmset_result is not None:
                return pmset_result

        # 3. psutil fallback
        try:
            import psutil

            batt = psutil.sensors_battery()
            if batt:
                return {
                    "battery_level_percent": round(float(batt.percent), 1),
                    "is_on_ac": bool(batt.power_plugged),
                    "charging": bool(batt.power_plugged),
                }
        except Exception as e:
            logger.debug("psutil battery query failed: %s", e)

        # 4. Safe default (assume desktop/wall power)
        return {
            "battery_level_percent": 100.0,
            "is_on_ac": True,
            "charging": True,
        }

    def _read_pmset_battery(self) -> dict[str, Any] | None:
        """Parse battery status from `pmset -g batt`."""
        try:
            res = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
            output = res.stdout.strip()
            if not output:
                return None

            lower_out = output.lower()
            is_on_ac = "ac power" in lower_out

            # Extract percentage (e.g. "94%")
            battery_pct = 100.0
            match = re.search(r"(\d+)%", output)
            if match:
                battery_pct = float(match.group(1))

            # Determine charging state (note: 'discharging' contains 'charging' as substring)
            is_discharging = "discharging" in lower_out
            if is_discharging:
                charging = False
            else:
                charging = (
                    "charging" in lower_out
                    or "finishing charge" in lower_out
                    or is_on_ac
                )

            return {
                "battery_level_percent": round(battery_pct, 1),
                "is_on_ac": is_on_ac,
                "charging": charging,
            }
        except Exception as e:
            logger.debug("pmset -g batt error: %s", e)
            return None

    def _read_sysfs_battery(self) -> dict[str, Any] | None:
        """Read battery information from a sysfs directory."""
        if not self.sysfs_path:
            return None

        # Look in sysfs_path or sysfs_path / power_supply
        power_dir = self.sysfs_path / "power_supply"
        if not power_dir.exists():
            power_dir = self.sysfs_path

        battery_pct = 100.0
        is_on_ac = True
        charging = False

        found_battery = False

        # Look for battery subdirs (e.g. BAT0, battery) or directly capacity file
        candidates = [power_dir] + [p for p in power_dir.iterdir() if p.is_dir()]
        for cand in candidates:
            cap_file = cand / "capacity"
            if cap_file.exists():
                try:
                    battery_pct = float(cap_file.read_text().strip())
                    found_battery = True
                except ValueError:
                    pass

            status_file = cand / "status"
            if status_file.exists():
                status_text = status_file.read_text().strip().lower()
                if "discharging" in status_text:
                    charging = False
                    is_on_ac = False
                elif "charging" in status_text and "not charging" not in status_text:
                    charging = True
                    is_on_ac = True
                elif "full" in status_text:
                    charging = False
                    is_on_ac = True

            online_file = cand / "online"
            if online_file.exists():
                try:
                    val = online_file.read_text().strip()
                    is_on_ac = val == "1"
                    if is_on_ac:
                        charging = True
                except Exception:
                    pass

        # Check explicit ac adapter subdir (e.g. AC, ACAD)
        for name in ("AC", "ACAD", "ADP1", "adapter"):
            ac_file = power_dir / name / "online"
            if ac_file.exists():
                try:
                    is_on_ac = ac_file.read_text().strip() == "1"
                    if not is_on_ac:
                        charging = False
                except Exception:
                    pass

        if found_battery or charging or not is_on_ac:
            return {
                "battery_level_percent": round(battery_pct, 1),
                "is_on_ac": is_on_ac,
                "charging": charging,
            }
        return None

    # -------------------------------------------------------------------------
    # Thermal Pressure Detection
    # -------------------------------------------------------------------------

    def get_thermal_pressure(self) -> str:
        """Query thermal pressure level ('nominal', 'moderate', 'heavy', 'critical').

        Returns:
            Normalized thermal pressure string.
        """
        # 1. Simulated sysfs check
        if self.sysfs_path and self.sysfs_path.exists():
            sysfs_therm = self._read_sysfs_thermal()
            if sysfs_therm is not None:
                return sysfs_therm

        # 2. macOS pmset -g therm
        if shutil.which("pmset"):
            try:
                res = subprocess.run(
                    ["pmset", "-g", "therm"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3,
                )
                output = res.stdout.lower()
                if "critical" in output or "level: 3" in output or "trapping" in output:
                    return "critical"
                if "heavy" in output or "level: 2" in output:
                    return "heavy"
                if "moderate" in output or "level: 1" in output:
                    return "moderate"
                if "nominal" in output or "no thermal warning level" in output:
                    return "nominal"
            except Exception as e:
                logger.debug("pmset -g therm error: %s", e)

        # 3. Load average fallback
        try:
            load_1m, _, _ = os.getloadavg()
            cpu_count = os.cpu_count() or 4
            ratio = load_1m / max(1, cpu_count)
            if ratio >= 2.5:
                return "critical"
            if ratio >= 1.75:
                return "heavy"
            if ratio >= 1.0:
                return "moderate"
            return "nominal"
        except Exception:
            return "nominal"

    def _read_sysfs_thermal(self) -> str | None:
        """Read thermal state from simulated sysfs."""
        if not self.sysfs_path:
            return None

        for path in (
            self.sysfs_path / "thermal_pressure",
            self.sysfs_path / "thermal" / "thermal_pressure",
            self.sysfs_path / "thermal_state",
        ):
            if path.exists():
                content = path.read_text().strip().lower()
                if content in {"nominal", "moderate", "heavy", "critical"}:
                    return content

        # Check millidegree temperature file (e.g. temp in /sys/class/thermal/thermal_zone0/temp)
        temp_files = list(self.sysfs_path.glob("**/temp"))
        for temp_file in temp_files:
            try:
                val = int(temp_file.read_text().strip())
                temp_c = val / 1000.0 if val > 1000 else float(val)
                if temp_c >= 95.0:
                    return "critical"
                if temp_c >= 85.0:
                    return "heavy"
                if temp_c >= 70.0:
                    return "moderate"
                return "nominal"
            except Exception:
                pass

        return None

    # -------------------------------------------------------------------------
    # Clamshell / Display State
    # -------------------------------------------------------------------------

    def get_clamshell_state(self) -> dict[str, Any]:
        """Detect Mac lid clamshell closure state and display activity.

        Returns:
            Dict containing:
                - clamshell_closed (bool): True if laptop lid is closed.
                - display_active (bool): True if display is active.
                - state (str): "closed" or "open".
        """
        # 1. Simulated sysfs
        if self.sysfs_path and self.sysfs_path.exists():
            for name in ("clamshell", "clamshell_state", "lid"):
                p = self.sysfs_path / name
                if p.exists():
                    val = p.read_text().strip().lower()
                    closed = val in {"1", "yes", "true", "closed"}
                    return {
                        "clamshell_closed": closed,
                        "display_active": not closed,
                        "state": "closed" if closed else "open",
                    }

        # 2. macOS ioreg lookup
        if shutil.which("ioreg"):
            try:
                res = subprocess.run(
                    ["ioreg", "-r", "-k", "AppleClamshellState"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3,
                )
                output = res.stdout
                for line in output.splitlines():
                    if "AppleClamshellState" in line:
                        closed = "yes" in line.lower()
                        return {
                            "clamshell_closed": closed,
                            "display_active": not closed,
                            "state": "closed" if closed else "open",
                        }
            except Exception as e:
                logger.debug("ioreg clamshell query error: %s", e)

        # Default: open and active
        return {
            "clamshell_closed": False,
            "display_active": True,
            "state": "open",
        }

    # -------------------------------------------------------------------------
    # Memory & CPU Load
    # -------------------------------------------------------------------------

    def get_memory_metrics(self) -> dict[str, float]:
        """Retrieve host RAM allocation metrics.

        Returns:
            Dict with host_ram_used_gb, host_ram_total_gb, and host_ram_percent.
        """
        try:
            import psutil

            vm = psutil.virtual_memory()
            total_gb = round(vm.total / (1024**3), 1)
            used_gb = round(vm.used / (1024**3), 1)
            percent = round(float(vm.percent), 1)
            return {
                "host_ram_used_gb": used_gb,
                "host_ram_total_gb": total_gb,
                "host_ram_percent": percent,
            }
        except Exception as e:
            logger.debug("psutil memory query error: %s", e)

        # Conservative fallback
        return {
            "host_ram_used_gb": 8.0,
            "host_ram_total_gb": 16.0,
            "host_ram_percent": 50.0,
        }

    def get_cpu_load(self) -> float:
        """Retrieve host CPU utilization percentage.

        Returns:
            CPU load percentage (0.0 to 100.0).
        """
        try:
            import psutil

            cpu_val = psutil.cpu_percent(interval=None)
            if cpu_val > 0.0:
                return round(float(cpu_val), 1)
        except Exception as e:
            logger.debug("psutil cpu query error: %s", e)

        try:
            load_1m, _, _ = os.getloadavg()
            cpu_count = os.cpu_count() or 4
            pct = min(100.0, round((load_1m / max(1, cpu_count)) * 100.0, 1))
            return pct
        except Exception:
            return 25.0

    # -------------------------------------------------------------------------
    # Execution Eligibility & Telemetry Snapshot
    # -------------------------------------------------------------------------

    def check_execution_eligibility(
        self,
        battery_level: float | None = None,
        is_on_ac: bool | None = None,
        thermal_pressure: str | None = None,
    ) -> tuple[bool, str]:
        """Check whether the node is healthy enough to execute autonomous tasks.

        Rules:
            - Eligible (True, 'Eligible') if:
                (battery >= min_battery_percent OR is_on_ac) AND thermal_pressure != 'critical'
            - Ineligible (False, reason) if:
                thermal_pressure == 'critical' OR (battery < min_battery_percent AND not is_on_ac)

        Args:
            battery_level: Optional battery percentage override for testing.
            is_on_ac: Optional AC power state override for testing.
            thermal_pressure: Optional thermal state override for testing.

        Returns:
            Tuple of (is_eligible: bool, reason: str).
        """
        if battery_level is None or is_on_ac is None:
            batt_info = self.get_battery_state()
            if battery_level is None:
                battery_level = batt_info["battery_level_percent"]
            if is_on_ac is None:
                is_on_ac = batt_info["is_on_ac"]

        if thermal_pressure is None:
            thermal_pressure = self.get_thermal_pressure()

        norm_thermal = thermal_pressure.lower().strip()
        if norm_thermal == "critical":
            return False, f"Thermal pressure is critical ({norm_thermal})"

        if not is_on_ac and battery_level < self.min_battery_percent:
            return (
                False,
                f"Battery level is below {self.min_battery_percent:.0f}% ({battery_level:.1f}%) "
                "and not connected to AC power",
            )

        return True, "Eligible"

    def get_hardware_telemetry_snapshot(self) -> dict[str, Any]:
        """Produce a complete telemetry dictionary structured for HardwareTelemetryScreen.tsx.

        Returns:
            Dictionary matching the frontend HardwareTelemetry TypeScript interface:
                - host_cpu_percent (float)
                - host_ram_percent (float)
                - host_ram_used_gb (float)
                - host_ram_total_gb (float)
                - thermal_pressure (str)
                - battery_level_percent (float)
                - battery_charging (bool)
                - usb_device_connected (bool)
                - usb_device_serial (str)
                - usb_device_name (str)
                Plus supplementary fields:
                - clamshell_closed (bool)
                - display_active (bool)
                - is_on_ac (bool)
                - execution_eligible (bool)
                - eligibility_reason (str)
        """
        batt = self.get_battery_state()
        thermal = self.get_thermal_pressure()
        clamshell = self.get_clamshell_state()
        mem = self.get_memory_metrics()
        cpu = self.get_cpu_load()
        eligible, reason = self.check_execution_eligibility(
            battery_level=batt["battery_level_percent"],
            is_on_ac=batt["is_on_ac"],
            thermal_pressure=thermal,
        )

        return {
            "host_cpu_percent": cpu,
            "host_ram_percent": mem["host_ram_percent"],
            "host_ram_used_gb": mem["host_ram_used_gb"],
            "host_ram_total_gb": mem["host_ram_total_gb"],
            "thermal_pressure": thermal,
            "battery_level_percent": batt["battery_level_percent"],
            "battery_charging": batt["charging"],
            "usb_device_connected": True,
            "usb_device_serial": self.usb_serial,
            "usb_device_name": self.usb_device_name,
            "is_usb_device_present": True,
            "clamshell_closed": clamshell["clamshell_closed"],
            "display_active": clamshell["display_active"],
            "is_on_ac": batt["is_on_ac"],
            "execution_eligible": eligible,
            "eligibility_reason": reason,
        }
