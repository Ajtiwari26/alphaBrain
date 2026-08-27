"""
testscript/test_preview_supervisor.py
Deterministic unit tests for PreviewSupervisor:
- Startup readiness and 200-level non-empty body verification.
- Empty/invalid response rejection.
- Clean child process group teardown.
- Managed health failure detection and restart.
- Persisted metadata lifecycle.
- Reclaiming/adopting proven healthy AlphaBrain-owned listener.
- Terminating & restarting proven unhealthy AlphaBrain-owned listener.
- Exact legacy command matching reclaim.
- Unknown-process non-kill guarantee.
"""

import signal

import pytest

from alpha_worker.preview import (
    PreviewMetadata,
    PreviewStatus,
    PreviewSupervisor,
)


class FakePopen:
    def __init__(self, pid: int = 10101, returncode: int | None = None):
        self.pid = pid
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -signal.SIGTERM

    def kill(self):
        self.killed = True
        self.returncode = -signal.SIGKILL


def test_preview_startup_and_healthy_200_body(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "index.html").write_text(
        "<!DOCTYPE html><html><body>Scientific Calculator</body></html>"
    )

    fake_proc = FakePopen(pid=20001)

    supervisor = PreviewSupervisor(
        state_dir=tmp_path / "state",
        http_checker=lambda url, timeout: (
            200,
            b"<!DOCTYPE html><html><body>Scientific Calculator</body></html>",
        ),
        process_launcher=lambda cmd, cwd: fake_proc,
    )

    metadata = supervisor.start_preview(
        worktree,
        task_id="tsk_calc_01",
        project_id="prj_calc",
        port=9876,
        timeout_seconds=2.0,
    )

    assert metadata.status == PreviewStatus.HEALTHY
    assert metadata.pid == 20001
    assert metadata.port == 9876
    assert metadata.url == "http://127.0.0.1:9876/"
    assert metadata.health_error is None
    assert metadata.started_at is not None
    assert metadata.last_health_check_at is not None

    persisted = supervisor.load_persisted_metadata("tsk_calc_01")
    assert persisted is not None
    assert persisted.pid == 20001
    assert persisted.status == PreviewStatus.HEALTHY


def test_preview_rejects_empty_response_body(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "index.html").write_text("")

    fake_proc = FakePopen(pid=20002)
    killed_pids = []

    def fake_killpg(pid, sig):
        killed_pids.append((pid, sig))
        fake_proc.returncode = -sig

    monkeypatch.setattr("os.killpg", fake_killpg)

    supervisor = PreviewSupervisor(
        state_dir=tmp_path / "state",
        http_checker=lambda url, timeout: (200, b""),
        process_launcher=lambda cmd, cwd: fake_proc,
    )

    with pytest.raises(RuntimeError, match="empty response body"):
        supervisor.start_preview(
            worktree,
            task_id="tsk_calc_empty",
            project_id="prj_calc",
            port=9877,
            timeout_seconds=0.5,
        )

    assert any(pid == 20002 for pid, _ in killed_pids)


def test_preview_rejects_non_2xx_status_code(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    fake_proc = FakePopen(pid=20003)
    killed_pids = []

    def fake_killpg(pid, sig):
        killed_pids.append((pid, sig))
        fake_proc.returncode = -sig

    monkeypatch.setattr("os.killpg", fake_killpg)

    supervisor = PreviewSupervisor(
        state_dir=tmp_path / "state",
        http_checker=lambda url, timeout: (500, b"Internal Server Error"),
        process_launcher=lambda cmd, cwd: fake_proc,
    )

    with pytest.raises(RuntimeError, match="500 is not a successful 2xx response"):
        supervisor.start_preview(
            worktree,
            task_id="tsk_calc_500",
            project_id="prj_calc",
            port=9878,
            timeout_seconds=0.5,
        )

    assert any(pid == 20003 for pid, _ in killed_pids)


def test_preview_clean_child_process_group_teardown(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    fake_proc = FakePopen(pid=20004)
    killed_signals = []

    def fake_killpg(pid, sig):
        killed_signals.append((pid, sig))
        fake_proc.returncode = -sig

    monkeypatch.setattr("os.killpg", fake_killpg)

    supervisor = PreviewSupervisor(
        state_dir=tmp_path / "state",
        http_checker=lambda url, timeout: (200, b"content"),
        process_launcher=lambda cmd, cwd: fake_proc,
    )

    metadata = supervisor.start_preview(
        worktree,
        task_id="tsk_calc_term",
        project_id="prj_calc",
        port=9879,
        timeout_seconds=1.0,
    )
    assert metadata.status == PreviewStatus.HEALTHY

    supervisor.terminate_preview(metadata)
    assert metadata.status == PreviewStatus.STOPPED
    assert (20004, signal.SIGTERM) in killed_signals


def test_preview_restart_after_managed_health_failure(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    proc1 = FakePopen(pid=20005)
    proc2 = FakePopen(pid=20006)
    spawn_count = 0

    def fake_launcher(cmd, cwd):
        nonlocal spawn_count
        spawn_count += 1
        return proc1 if spawn_count == 1 else proc2

    http_responses = [(200, b"Initial Good Body")]

    def fake_http_checker(url, timeout):
        if http_responses:
            return http_responses.pop(0)
        return 500, b"Crash"

    killed_pids = []

    def fake_killpg(pid, sig):
        killed_pids.append((pid, sig))
        if pid == 20005:
            proc1.returncode = -sig
        if pid == 20006:
            proc2.returncode = -sig

    monkeypatch.setattr("os.killpg", fake_killpg)

    supervisor = PreviewSupervisor(
        state_dir=tmp_path / "state",
        http_checker=fake_http_checker,
        process_launcher=fake_launcher,
    )

    # 1. Start healthy
    metadata = supervisor.start_preview(
        worktree,
        task_id="tsk_calc_restart",
        project_id="prj_calc",
        port=9880,
        timeout_seconds=1.0,
    )
    assert metadata.status == PreviewStatus.HEALTHY
    assert metadata.pid == 20005

    # 2. Check health -> now fails with 500
    is_healthy = supervisor.check_health(metadata)
    assert is_healthy is False
    assert metadata.status == PreviewStatus.UNHEALTHY

    # 3. Restart preview -> queued new response
    http_responses.append((200, b"Recovered Body Content"))
    restarted_metadata = supervisor.restart_unhealthy_preview(metadata, timeout_seconds=1.0)

    assert restarted_metadata.status == PreviewStatus.HEALTHY
    assert restarted_metadata.pid == 20006
    assert restarted_metadata.restart_count == 1
    assert any(pid == 20005 for pid, _ in killed_pids)


def test_reclaim_healthy_persisted_preview_on_occupied_port(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    # Port is occupied by PID 30001
    monkeypatch.setattr(
        "alpha_worker.preview.is_port_available", lambda port, host="127.0.0.1": False
    )

    state_dir = tmp_path / "state"
    supervisor = PreviewSupervisor(
        state_dir=state_dir,
        http_checker=lambda url, timeout: (200, b"<!DOCTYPE html><h1>Calculator App</h1>"),
        port_owner_finder=lambda port: 30001,
        process_inspector=lambda pid: {
            "pid": 30001,
            "command": "python3 -m http.server 4173 --bind 127.0.0.1",
            "cwd": str(worktree.resolve()),
        },
    )

    # Save matching persisted record
    persisted = PreviewMetadata(
        task_id="tsk_calc_reclaim",
        project_id="prj_calc",
        worktree_path=worktree,
        port=4173,
        pid=30001,
        status=PreviewStatus.HEALTHY,
    )
    supervisor.save_persisted_metadata(persisted)

    # Calling start_preview on the occupied port should adopt it without spawning
    metadata = supervisor.start_preview(
        worktree,
        task_id="tsk_calc_reclaim",
        project_id="prj_calc",
        port=4173,
    )

    assert metadata.status == PreviewStatus.HEALTHY
    assert metadata.pid == 30001
    assert metadata.port == 4173
    assert metadata.url == "http://127.0.0.1:4173/"


def test_reclaim_legacy_command_matching_preview(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    # Port occupied by legacy process matching exact http.server command and worktree
    monkeypatch.setattr(
        "alpha_worker.preview.is_port_available", lambda port, host="127.0.0.1": False
    )

    state_dir = tmp_path / "state"
    supervisor = PreviewSupervisor(
        state_dir=state_dir,
        http_checker=lambda url, timeout: (200, b"Legacy Server Response"),
        port_owner_finder=lambda port: 30002,
        process_inspector=lambda pid: {
            "pid": 30002,
            "command": "/usr/local/bin/python3 -m http.server 4173 --bind 127.0.0.1",
            "cwd": str(worktree.resolve()),
        },
    )

    # No persisted metadata yet (first run after restart)
    metadata = supervisor.start_preview(
        worktree,
        task_id="tsk_calc_legacy",
        project_id="prj_calc",
        port=4173,
    )

    assert metadata.status == PreviewStatus.HEALTHY
    assert metadata.pid == 30002
    assert metadata.port == 4173
    assert metadata.url == "http://127.0.0.1:4173/"


def test_reclaim_unhealthy_owned_preview_terminates_and_restarts(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    killed_pids = []

    def fake_killpg(pid, sig):
        killed_pids.append((pid, sig))

    monkeypatch.setattr("os.killpg", fake_killpg)

    port_busy = True

    def fake_is_port_available(port, host="127.0.0.1"):
        return not port_busy

    monkeypatch.setattr("alpha_worker.preview.is_port_available", fake_is_port_available)

    fresh_proc = FakePopen(pid=30004)

    def fake_launcher(cmd, cwd):
        nonlocal port_busy
        port_busy = True
        return fresh_proc

    # Unhealthy initially (500), then healthy after new spawn
    responses = [(500, b"Hanging / Broken"), (200, b"Healthy Fresh Content")]

    def fake_http_checker(url, timeout):
        if responses:
            return responses.pop(0)
        return 200, b"Healthy Fresh Content"

    state_dir = tmp_path / "state"
    supervisor = PreviewSupervisor(
        state_dir=state_dir,
        http_checker=fake_http_checker,
        process_launcher=fake_launcher,
        port_owner_finder=lambda port: 30003,
        process_inspector=lambda pid: {
            "pid": 30003,
            "command": "python3 -m http.server 4173",
            "cwd": str(worktree.resolve()),
        },
    )

    metadata = supervisor.start_preview(
        worktree,
        task_id="tsk_calc_unhealthy_reclaim",
        project_id="prj_calc",
        port=4173,
    )

    # 30003 was terminated
    assert any(pid == 30003 for pid, _ in killed_pids)
    assert metadata.status == PreviewStatus.HEALTHY
    assert metadata.pid == 30004


def test_unknown_port_listener_is_never_killed(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    killed_pids = []

    def fake_killpg(pid, sig):
        killed_pids.append((pid, sig))

    monkeypatch.setattr("os.killpg", fake_killpg)
    monkeypatch.setattr(
        "alpha_worker.preview.is_port_available", lambda port, host="127.0.0.1": False
    )

    state_dir = tmp_path / "state"
    supervisor = PreviewSupervisor(
        state_dir=state_dir,
        port_owner_finder=lambda port: 99999,
        process_inspector=lambda pid: {
            "pid": 99999,
            "command": "postgres -D /usr/local/var/postgres",
            "cwd": "/usr/local/var/postgres",
        },
    )

    with pytest.raises(RuntimeError, match="unknown listener"):
        supervisor.start_preview(
            worktree,
            task_id="tsk_calc_unknown",
            project_id="prj_calc",
            port=5432,
        )

    # Crucial safety check: Unknown process was NEVER killed!
    assert len(killed_pids) == 0
