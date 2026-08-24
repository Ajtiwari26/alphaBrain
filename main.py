"""
main.py: Unified CLI and runtime entrypoint for Alpha Brain.
"""

# ruff: noqa: E402

import os
import sys
from pathlib import Path

# Automatically activate and re-exec using local .venv if not already inside it
venv_dir = Path(__file__).resolve().parent / ".venv"
if venv_dir.exists() and sys.prefix != str(venv_dir):
    venv_python = venv_dir / "bin" / "python"
    os.environ["PYTHONPATH"] = str(Path(__file__).resolve().parent)
    os.execv(str(venv_python), [str(venv_python), *sys.argv])

import argparse
import asyncio

import uvicorn

from alpha_core.config import settings
from alpha_core.db.connection import init_db
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.health import HardwareHealthChecker


def start_server(host: str = "127.0.0.1", port: int = 8000):
    print(f"🚀 Starting Alpha Brain Master API on http://{host}:{port}")
    print(f"📹 Open 3-Way Meeting Room at: http://localhost:{port}/meet")
    uvicorn.run("alpha_core.api.app:app", host=host, port=port, reload=settings.DEBUG)


async def run_worker():
    print(f"⚡ Starting Alpha Mac Worker Daemon [Device ID: {settings.ATTACHED_DEVICE_ID}]")
    await init_db()
    daemon = AlphaWorkerDaemon(worker_id="mac_worker_local")
    await daemon.run_loop(poll_interval_seconds=3)


def check_health():
    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    print("==========================================")
    print("🛡️  Alpha Brain Local Hardware Health")
    print("==========================================")
    print(f"Status:        {health.value.upper()}")
    print(f"AC Power:      {metrics.get('is_ac_power')}")
    print(f"Battery:       {metrics.get('battery_percentage')}%")
    print(f"Thermal Load:  {metrics.get('thermal_state').upper()}")
    print(f"Device:        {settings.ATTACHED_DEVICE_ID}")
    print("==========================================")


def main():
    parser = argparse.ArgumentParser(description="Alpha Brain Master CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the master FastAPI server")
    server_parser.add_argument("--host", default="127.0.0.1", help="Host address")
    server_parser.add_argument("--port", type=int, default=8000, help="Port number")

    # Worker command
    subparsers.add_parser("worker", help="Start the local background worker daemon")

    # Health command
    subparsers.add_parser("health", help="Check hardware power, thermal, and battery status")

    args = parser.parse_args()

    if args.command == "server":
        start_server(host=args.host, port=args.port)
    elif args.command == "worker":
        asyncio.run(run_worker())
    elif args.command == "health":
        check_health()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
