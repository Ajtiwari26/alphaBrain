"""Regression test: detached AGY descendants must not stall Alpha Brain."""

import asyncio
import json
import os

import pytest

from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge


def test_agy_turn_returns_when_child_keeps_inherited_output_open(tmp_path):
    fake_agy = tmp_path / "fake-agy"
    conversation_id = "00000000-0000-0000-0000-000000000003"
    fake_agy.write_text(
        "#!/bin/sh\n"
        'found_sandbox=false; for arg in "$@"; do [ "$arg" != "--sandbox" ] || found_sandbox=true; done; $found_sandbox || exit 98\n'
        "[ -d .gemini/antigravity-ide/brain ] || exit 99\n"
        "printf transient > .gemini/antigravity-ide/brain/turn-state\n"
        f"printf '%s\\n' '{json.dumps({'event': 'init', 'conversation_id': conversation_id})}'\n"
        "(sleep 20) &\n"
        f"printf '%s\\n' '{json.dumps({'event': 'result', 'result': {'conversation_id': conversation_id, 'status': 'SUCCESS', 'response': 'done'}})}'\n"
    )
    fake_agy.chmod(0o755)
    bridge = AntigravityLiveBridge()
    bridge.agy_bin = fake_agy

    result = asyncio.run(
        bridge._run_agy(
            prompt="test",
            worktree_path=tmp_path,
            conversation_id=None,
            is_new_project=True,
            timeout_seconds=60,
            log_path=tmp_path / "agy.json",
        )
    )

    assert result["returncode"] == 0
    permissions = json.loads((tmp_path / ".agents/settings.json").read_text())["permissions"][
        "allow"
    ]
    assert "mcp_*(*)" not in permissions
    assert "call_mcp_tool(*)" not in permissions
    assert not (tmp_path / ".gemini/antigravity-ide/brain").exists()
    assert result["events"][0]["conversation_id"] == conversation_id
    assert "SUCCESS" in (tmp_path / "agy.json").read_text()


def test_agy_turn_rejects_stale_task_brain(tmp_path):
    brain = tmp_path / ".gemini/antigravity-ide/brain"
    brain.mkdir(parents=True)
    bridge = AntigravityLiveBridge()

    with pytest.raises(RuntimeError, match="stale AGY brain"):
        asyncio.run(
            bridge._run_agy(
                prompt="test",
                worktree_path=tmp_path,
                conversation_id=None,
                is_new_project=True,
                timeout_seconds=60,
            )
        )


@pytest.mark.asyncio
async def test_cancelled_agy_turn_kills_process_group(tmp_path):
    fake_agy = tmp_path / "fake-agy-cancellable"
    pid_path = tmp_path / "agy.pid"
    import sys

    fake_agy.write_text(
        f"#!{sys.executable}\n"
        "import os\n"
        "import time\n"
        f"with open({str(pid_path)!r}, 'w') as f:\n"
        "    f.write(str(os.getpid()))\n"
        "    f.flush()\n"
        "time.sleep(30)\n"
    )
    fake_agy.chmod(0o755)
    bridge = AntigravityLiveBridge()
    bridge.agy_bin = fake_agy
    turn = asyncio.create_task(
        bridge._run_agy(
            prompt="test cancellation",
            worktree_path=tmp_path,
            conversation_id=None,
            is_new_project=True,
            timeout_seconds=60,
        )
    )
    for _ in range(100):
        if pid_path.exists():
            break
        await asyncio.sleep(0.05)
    assert pid_path.exists()
    pid = int(pid_path.read_text())

    turn.cancel()
    with pytest.raises(asyncio.CancelledError):
        await turn

    for _ in range(100):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.05)
    else:
        pytest.fail("Cancelled AGY process group remained alive")
