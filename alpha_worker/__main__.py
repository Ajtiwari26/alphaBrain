"""AlphaBrain Worker CLI: run daemon or operate durable local pause switch."""

import argparse
import asyncio
import getpass
import json
import signal

from alpha_core.config import settings

from .credentials import MacOSKeychain
from .daemon import AlphaWorkerDaemon
from .runtime_control import WorkerControlStore


def _control_store() -> WorkerControlStore:
    return WorkerControlStore(settings.WORKER_STATE_DIR)


async def _run_worker(poll_seconds: int) -> None:
    daemon = AlphaWorkerDaemon()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, setattr, daemon, "running", False)
    await daemon.run_loop(poll_interval_seconds=poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m alpha_worker")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run", help="run worker daemon")
    run.add_argument("--poll-seconds", type=int, default=5)
    pause = subcommands.add_parser("pause", help="persistently pause task intake")
    pause.add_argument("--reason", default="operator_requested")
    subcommands.add_parser("resume", help="resume task intake")
    subcommands.add_parser("status", help="read local worker control state")
    credentials = subcommands.add_parser(
        "credentials", help="store worker secrets in macOS Keychain"
    )
    credentials.add_argument(
        "account", choices=("worker-token", "worker-identity", "worker-spool-fernet-key")
    )
    args = parser.parse_args()
    store = _control_store()
    if args.command == "run":
        asyncio.run(_run_worker(args.poll_seconds))
    elif args.command == "pause":
        print(json.dumps(store.pause(args.reason).__dict__))
    elif args.command == "resume":
        print(json.dumps(store.resume().__dict__))
    elif args.command == "credentials":
        secret = getpass.getpass(f"Secret for {args.account}: ")
        MacOSKeychain(settings.WORKER_KEYCHAIN_SERVICE).set(args.account, secret)
        print(json.dumps({"stored": args.account, "service": settings.WORKER_KEYCHAIN_SERVICE}))
    else:
        import subprocess

        from .launchd_status import LaunchdInspector

        def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode, res.stdout, res.stderr

        inspector = LaunchdInspector(
            command_runner=run_cmd,
            status_file=settings.WORKER_STATE_DIR / "node_status.json",
        )
        report = inspector.inspect()
        out = store.read().__dict__
        out["launchd"] = report.__dict__
        print(json.dumps(out))


if __name__ == "__main__":
    main()
