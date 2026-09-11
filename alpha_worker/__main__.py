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
    credentials.add_argument("account", choices=("worker-token", "worker-spool-fernet-key"))

    supervisor_cmd = subcommands.add_parser(
        "supervisor", help="run persistent CI/CD healing and worker supervisor"
    )
    supervisor_cmd.add_argument("--poll-interval", type=float, default=1.0)
    supervisor_cmd.add_argument("--max-workers", type=int, default=4)
    supervisor_cmd.add_argument("--project-id", default="alphabrain_dogfood")
    supervisor_cmd.add_argument("--mode", choices=("thread", "subprocess"), default="thread")
    supervisor_cmd.add_argument("--max-cycles", type=int, default=None)

    subcommands.add_parser(
        "supervisor-status", help="inspect persistent supervisor status and health"
    )

    healing_cmd = subcommands.add_parser(
        "healing-daemon", help="run standalone CI healing daemon"
    )
    healing_cmd.add_argument("--project-id", default="alphabrain_dogfood")
    healing_cmd.add_argument("--poll-interval", type=float, default=10.0)

    disp_cmd = subcommands.add_parser(
        "dispatcher", help="run standalone parallel worker dispatcher"
    )
    disp_cmd.add_argument("--project-id", default="alphabrain_dogfood")
    disp_cmd.add_argument("--max-workers", type=int, default=4)
    disp_cmd.add_argument("--poll-interval", type=float, default=1.0)
    disp_cmd.add_argument("--max-cycles", type=int, default=None)

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
    elif args.command == "supervisor":
        from .daemon_supervisor import DaemonSupervisor

        supervisor = DaemonSupervisor.create_healing_supervisor(
            project_id=args.project_id,
            max_workers=args.max_workers,
            poll_interval=args.poll_interval,
            execution_mode=args.mode,
        )
        supervisor.start()
        supervisor.run_loop(poll_interval=args.poll_interval, max_cycles=args.max_cycles)
    elif args.command == "supervisor-status":
        from .daemon_supervisor import DaemonSupervisor, HealingLaunchdInspector

        status_path = settings.WORKER_STATE_DIR / "supervisor_status.json"
        report = DaemonSupervisor.read_status_file(status_path)
        inspector = HealingLaunchdInspector()
        out = {
            "supervisor": report or {"status": "not_running"},
            "launchd": inspector.inspect(),
        }
        print(json.dumps(out, indent=2))
    elif args.command == "healing-daemon":
        from alpha_core.queue.triage_queue import TaskTriageQueue

        from .ci_healing_daemon import CIHealingDaemon

        daemon = CIHealingDaemon(
            queue=TaskTriageQueue(),
            project_id=args.project_id,
            auto_approve_repairs=True,
        )
        daemon.run_continuously(interval=args.poll_interval)
    elif args.command == "dispatcher":
        from alpha_core.queue.triage_queue import TaskTriageQueue

        from .parallel_dispatcher import ParallelWorkerDispatcher

        dispatcher = ParallelWorkerDispatcher(
            queue=TaskTriageQueue(),
            max_workers=args.max_workers,
            project_id=args.project_id,
            poll_interval=args.poll_interval,
        )
        dispatcher.run_continuously(interval=args.poll_interval, max_cycles=args.max_cycles)
    else:
        import subprocess

        from .daemon_supervisor import DaemonSupervisor, HealingLaunchdInspector
        from .launchd_status import LaunchdInspector

        def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode, res.stdout, res.stderr

        inspector = LaunchdInspector(
            command_runner=run_cmd,
            status_file=settings.WORKER_STATE_DIR / "node_status.json",
        )
        healing_inspector = HealingLaunchdInspector(command_runner=run_cmd)
        report = inspector.inspect()
        out = store.read().__dict__
        out["launchd"] = report.__dict__
        status_file = settings.WORKER_STATE_DIR / "supervisor_status.json"
        out["supervisor"] = DaemonSupervisor.read_status_file(status_file)
        out["healing_launchd"] = healing_inspector.inspect()
        print(json.dumps(out))


if __name__ == "__main__":
    main()
