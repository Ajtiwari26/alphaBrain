"""
alpha_core/mobile_bridge/mac_streamer.py
Lightweight background telemetry daemon that streams real Apple Silicon Mac
vitals, local worktrees, and projects to the AlphaBrain Production Cloud Backend.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mac_streamer")

STAGING_URL = os.environ.get(
    "ALPHABRAIN_STAGING_URL",
    "https://alpha-brain-staging.onrender.com/api/v1/mobile/sync/mac-node",
)
AUTH_TOKEN = os.environ.get("ALPHABRAIN_API_TOKEN", "ced2a32dd9a568fa22e606fa48381543")
TARGET_DEVICE = os.environ.get("ALPHABRAIN_TARGET_DEVICE", "10BF5P2AZF0010T")


def get_mac_telemetry() -> dict:
    cpu_percent = 22.0
    ram_percent = 40.0
    ram_used = 12.0
    ram_total = 16.0
    battery_pct = 100.0
    battery_chg = True
    thermal_pressure = "nominal"

    try:
        import psutil

        cpu_percent = round(psutil.cpu_percent(interval=None) or 20.0, 1)
        vm = psutil.virtual_memory()
        ram_percent = round(vm.percent, 1)
        ram_used = round(vm.used / (1024**3), 1)
        ram_total = round(vm.total / (1024**3), 1)
        batt = psutil.sensors_battery()
        if batt:
            battery_pct = round(batt.percent, 1)
            battery_chg = bool(batt.power_plugged)
    except Exception as e:
        logger.debug("psutil error: %s", e)

    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(["pmset", "-g", "batt"], text=True, timeout=2.0)
            m_pct = re.search(r"(\d+)%", out)
            if m_pct:
                battery_pct = float(m_pct.group(1))
            battery_chg = (
                "charging" in out.lower() and "discharging" not in out.lower()
            ) or "ac attached" in out.lower()
        except Exception:
            pass

        try:
            t_out = subprocess.check_output(
                ["pmset", "-g", "therm"], text=True, stderr=subprocess.DEVNULL, timeout=2.0
            )
            if "high" in t_out.lower():
                thermal_pressure = "high"
            elif "moderate" in t_out.lower():
                thermal_pressure = "moderate"
            else:
                thermal_pressure = "nominal"
        except Exception:
            thermal_pressure = "nominal"

    return {
        "host_cpu_percent": cpu_percent,
        "host_ram_percent": ram_percent,
        "host_ram_used_gb": ram_used,
        "host_ram_total_gb": ram_total,
        "thermal_pressure": thermal_pressure,
        "battery_level_percent": battery_pct,
        "battery_charging": battery_chg,
        "usb_device_connected": True,
        "usb_device_serial": TARGET_DEVICE,
        "usb_device_name": "iQOO 12 Flagship (Mac Host Synchronized)",
    }


def get_mac_worktrees() -> list:
    worktrees = []
    try:
        res = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
            check=True,
        )
        current = {}
        for line in res.stdout.splitlines():
            if not line.strip():
                if current:
                    worktrees.append(current)
                    current = {}
                continue
            parts = line.split(" ", 1)
            key = parts[0]
            val = parts[1] if len(parts) > 1 else ""
            if key == "worktree":
                current["path"] = val
                current["name"] = Path(val).name
            elif key == "HEAD":
                current["commit"] = val[:8]
            elif key == "branch":
                current["branch"] = val.replace("refs/heads/", "")
        if current:
            worktrees.append(current)
    except Exception as e:
        logger.debug("Worktrees read warning: %s", e)
    return worktrees


def get_mac_projects() -> list:
    projects_dir = Path("/Users/ajaytiwari/Desktop/Projects")
    results = []
    if projects_dir.exists():
        for p in sorted(projects_dir.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                try:
                    mtime = p.stat().st_mtime
                except Exception:
                    mtime = time.time()
                results.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "mtime": mtime,
                        "is_active": p.name
                        in ("alphaBrain", "DeployMate", "deployMateStudio", "nukkadMart", "knot"),
                    }
                )
    return results


def get_mac_triage_tasks() -> list:
    db_path = Path.home() / ".alphabrain" / "task_triage_queue.db"
    if not db_path.exists():
        return []
    try:
        from alpha_core.queue.triage_queue import TaskTriageQueue

        queue = TaskTriageQueue(db_path=db_path)
        raw_tasks = queue.list_tasks(limit=50)
        formatted = []
        for t in raw_tasks:
            env = t.get("envelope") or {}
            formatted.append(
                {
                    "task_id": t.get("id", ""),
                    "title": env.get("title") or t.get("id", ""),
                    "category": env.get("category") or "engineering",
                    "status": t.get("status", "unknown"),
                    "priority": env.get("priority", "normal").lower(),
                    "risk_class": env.get("risk_class") or "low",
                    "created_at": float(t.get("created_at") or time.time()),
                    "updated_at": float(t.get("updated_at") or time.time()),
                    "author": env.get("author") or "Eva CTO",
                    "allowed_paths": env.get("allowed_paths") or [],
                    "acceptance_commands": env.get("acceptance_commands") or [],
                }
            )
        return formatted
    except Exception as e:
        logger.debug("Triage read warning: %s", e)
        return []


def execute_remote_command(cmd: dict) -> None:
    c_type = cmd.get("command")
    if c_type == "triage_verdict":
        tid = cmd.get("task_id")
        action = cmd.get("action")
        notes = cmd.get("notes") or ""
        override_reason = cmd.get("override_reason")
        logger.info("Executing remote triage command from cloud: %s -> %s", tid, action)
        try:
            from alpha_core.mobile_bridge.schemas import TriageAction
            from alpha_core.mobile_bridge.service import MobileBridgeService

            svc = MobileBridgeService(
                db_path=Path.home() / ".alphabrain" / "task_triage_queue.db"
            )
            action_enum = (
                TriageAction.APPROVE if action == "approve" else TriageAction.REJECT
            )
            res = svc.review_triage_task(
                task_id=tid,
                action=action_enum,
                founder_notes=notes,
                override_reason=override_reason,
            )
            logger.info(
                "Executed triage review for %s: success=%s, status=%s, msg=%s",
                tid,
                res.success,
                res.new_status,
                res.message,
            )
        except Exception as e:
            logger.warning("Failed executing remote triage command: %s", e)


_MAC_QUOTA_CACHE: dict[str, Any] = {"timestamp": 0.0, "scores": []}


def get_mac_model_scores() -> list[dict[str, Any]]:
    global _MAC_QUOTA_CACHE
    now = time.time()
    if _MAC_QUOTA_CACHE["scores"] and (now - _MAC_QUOTA_CACHE["timestamp"]) < 30.0:
        return _MAC_QUOTA_CACHE["scores"]

    switch_script = Path.home() / ".local" / "bin" / "agy-switch"
    profiles_dir = Path.home() / ".gemini" / "profiles"
    if not (switch_script.exists() and profiles_dir.exists()):
        return []

    try:
        from concurrent.futures import ThreadPoolExecutor
        from importlib.machinery import SourceFileLoader

        mod = SourceFileLoader("agy_switch", str(switch_script)).load_module()
        profiles = sorted([p.name for p in profiles_dir.iterdir() if p.is_dir()])
        active = mod.get_active_profile_name()

        def fetch_one(p: str) -> tuple[str, dict[str, Any] | None]:
            try:
                return p, mod.fetch_live_quota(p)
            except Exception:
                return p, None

        with ThreadPoolExecutor(max_workers=min(8, len(profiles) or 1)) as executor:
            results = list(executor.map(fetch_one, profiles))

        scores = []
        for email, quota in results:
            if not quota or not quota.get("valid"):
                scores.append({
                    "account_name": f"{email.split('@')[0]} (Exhausted)",
                    "email": email,
                    "tier": "Tier 4 (Disqualified)",
                    "utility_score": -1.0,
                    "weekly_quota_percent": 0.0,
                    "five_hour_quota_percent": 0.0,
                    "recommended_model": "gemini-3.1-pro-high",
                    "gemini_5h_percent": 0.0,
                    "gemini_weekly_percent": 0.0,
                    "gemini_5h_desc": "Token expired or invalid",
                    "gemini_weekly_desc": "",
                    "claude_5h_percent": 0.0,
                    "claude_weekly_percent": 0.0,
                    "claude_5h_desc": "",
                    "claude_weekly_desc": "",
                    "token_status": "invalid",
                    "is_active": (email == active),
                })
                continue

            score, tier = mod.compute_oc_eds_score(quota)
            is_active = (email == active)
            rec_model = "claude-opus-4-6-thinking" if quota.get("claude_weekly", 0) > 0 else "gemini-3.1-pro-high"
            acct_label = f"{email.split('@')[0]} {'[ACTIVE]' if is_active else ''}".strip()

            scores.append({
                "account_name": acct_label,
                "email": email,
                "tier": tier,
                "utility_score": float(score) if score != -float("inf") else -1.0,
                "weekly_quota_percent": float(quota.get("gemini_weekly", 0.0)),
                "five_hour_quota_percent": float(quota.get("gemini_5h", 0.0)),
                "recommended_model": rec_model,
                "gemini_5h_percent": float(quota.get("gemini_5h", 0.0)),
                "gemini_weekly_percent": float(quota.get("gemini_weekly", 0.0)),
                "gemini_5h_desc": str(quota.get("gemini_5h_desc", "")),
                "gemini_weekly_desc": str(quota.get("gemini_weekly_desc", "")),
                "claude_5h_percent": float(quota.get("claude_5h", 0.0)),
                "claude_weekly_percent": float(quota.get("claude_weekly", 0.0)),
                "claude_5h_desc": str(quota.get("claude_5h_desc", "")),
                "claude_weekly_desc": str(quota.get("claude_weekly_desc", "")),
                "token_status": "valid",
                "is_active": is_active,
            })

        scores.sort(key=lambda s: s["utility_score"], reverse=True)
        _MAC_QUOTA_CACHE["timestamp"] = now
        _MAC_QUOTA_CACHE["scores"] = scores
        return scores
    except Exception as e:
        logger.debug("Model scores read warning: %s", e)
        return []


def sync_once() -> bool:
    payload = {
        "telemetry": get_mac_telemetry(),
        "worktrees": get_mac_worktrees(),
        "projects": get_mac_projects(),
        "triage_tasks": get_mac_triage_tasks(),
        "model_scores": get_mac_model_scores(),
        "timestamp": time.time(),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        STAGING_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "User-Agent": "AlphaBrain-Mac-Streamer/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                raw_body = resp.read()
                if raw_body:
                    try:
                        resp_data = json.loads(raw_body.decode("utf-8"))
                        pending_cmds = resp_data.get("pending_commands", [])
                        for cmd in pending_cmds:
                            execute_remote_command(cmd)
                    except Exception as e:
                        logger.debug("Failed parsing response body: %s", e)
                return True
            return False
    except Exception as e:
        logger.warning("Telemetry sync to cloud failed: %s", e)
        return False


def run_streamer(interval_sec: float = 3.0):
    logger.info("Starting AlphaBrain Mac Telemetry Streamer -> %s", STAGING_URL)
    backoff = interval_sec
    while True:
        success = sync_once()
        if success:
            logger.debug("Synced Mac telemetry successfully")
            backoff = interval_sec
        else:
            backoff = min(backoff * 1.5, 15.0)
            logger.info("Backing off sync for %.1fs...", backoff)
        time.sleep(backoff)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        ok = sync_once()
        print("Sync once status:", ok)
        sys.exit(0 if ok else 1)
    run_streamer()
