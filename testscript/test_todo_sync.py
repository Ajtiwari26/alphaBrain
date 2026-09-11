"""
testscript/test_todo_sync.py
Unit tests for Autonomous TODO and Roadmap Synchronization Engine.
Verifies parsing, checklist updates, milestone migration, atomicity,
idempotency, and triage_cli.cmd_merge integration.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.automation.todo_sync import TodoSyncEngine, sync_task_completion
from alpha_core.queue.triage_queue import TriageStatus
from alpha_core.triage_cli import cmd_merge


@pytest.fixture
def sample_todo_content():
    return """# Alpha Brain Development TODO

## Current implementation baseline

### Implemented foundation

- [x] Alpha Protocol schemas (`commit 1111111`, `tsk_eva_init001`).
- [x] Strict tenant isolation (`commit 2222222`, `tsk_eva_init002`).

### Active / In-Progress

- [ ] Parallel Worker Dispatcher Daemon: concurrent task pool across isolated worktrees.
- [ ] Autonomous TODO and Roadmap State Machine Sync Engine.
- [ ] Async Redis token-bucket rate limiter for FastAPI endpoints (`tsk_eva_5fb3a94658b7`).
"""


@pytest.fixture
def sample_roadmap_content():
    return """# AlphaBrain Next Phase Roadmap: Self-Development Pipeline

## Completed & Merged Milestones (September 2026)

### Task 2: Sandbox & Daemon Isolation
- **Status**: `[x] COMPLETED & MERGED` (`commit 6e11eeb`, `tsk_eva_47cc21ccaea2`)
- **Objective**: Isolated autonomous coding worker inside restricted non-admin macOS user environment via `launchd`.

---

## Active Parallel Development Pipeline (Current)

### Task 7: Autonomous TODO and Roadmap State Machine Sync Engine
- **Task Title**: Implement Autonomous TODO and Roadmap Synchronization Engine
- **Objective**: Automatically parse merged task metadata upon atomic promotion and update TODO.md and roadmap.
- **Allowed Scope**: `alpha_core/automation/`, `alpha_core/triage_cli.py`
- **Acceptance Criteria**: Passing unit tests verifying markdown parsing.

### Task 8: Parallel Worker Dispatcher Daemon
- **Task Title**: Implement Parallel Worker Dispatcher Daemon
- **Objective**: Multi-worker pool.
"""


def test_todo_update_existing_item(tmp_path, sample_todo_content):
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(sample_todo_content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, todo_path=todo_file)
    task_id = "tsk_eva_37eceb12e1b8"
    commit_sha = "abcdef1234567890abcdef1234567890abcdef12"

    updated = engine.update_todo(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
    )
    assert updated is True

    result_text = todo_file.read_text(encoding="utf-8")
    assert f"- [x] Autonomous TODO and Roadmap State Machine Sync Engine (`commit abcdef1`, `{task_id}`)." in result_text
    assert "- [ ] Autonomous TODO and Roadmap State Machine Sync Engine." not in result_text


def test_todo_update_idempotency(tmp_path, sample_todo_content):
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(sample_todo_content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, todo_path=todo_file)
    task_id = "tsk_eva_37eceb12e1b8"
    commit_sha = "abcdef1234567890abcdef1234567890abcdef12"

    # First update
    res1 = engine.update_todo(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
    )
    assert res1 is True

    # Second update should be idempotent (no-op)
    res2 = engine.update_todo(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
    )
    assert res2 is False


def test_todo_update_by_task_id_in_line(tmp_path):
    todo_file = tmp_path / "TODO.md"
    content = """# TODO
### Active
- [ ] Rate limiter (`tsk_eva_5fb3a94658b7`).
"""
    todo_file.write_text(content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, todo_path=todo_file)
    task_id = "tsk_eva_5fb3a94658b7"
    commit_sha = "1234567890abcdef"

    updated = engine.update_todo(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Different Title",
    )
    assert updated is True

    text = todo_file.read_text(encoding="utf-8")
    assert "- [x]" in text
    assert "commit 1234567" in text
    assert task_id in text


def test_todo_update_item_not_found_appends(tmp_path, sample_todo_content):
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(sample_todo_content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, todo_path=todo_file)
    task_id = "tsk_eva_brand_new"
    commit_sha = "9999999888888"

    updated = engine.update_todo(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Brand New Feature",
    )
    assert updated is True

    text = todo_file.read_text(encoding="utf-8")
    assert f"- [x] Brand New Feature (`commit 9999999`, `{task_id}`)." in text


def test_roadmap_update_migrates_active_task_to_completed(tmp_path, sample_roadmap_content):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(sample_roadmap_content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    task_id = "tsk_eva_37eceb12e1b8"
    commit_sha = "abcdef1234567890abcdef1234567890abcdef12"

    updated = engine.update_roadmap(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
        objective="Automatically parse merged task metadata upon atomic promotion and update TODO.md and roadmap.",
    )
    assert updated is True

    text = roadmap_file.read_text(encoding="utf-8")

    # Verify task is now under Completed & Merged Milestones
    completed_pos = text.find("## Completed & Merged Milestones")
    divider_pos = text.find("---")
    task_pos = text.find("### Task 7: Autonomous TODO and Roadmap State Machine Sync Engine")
    active_pos = text.find("## Active Parallel Development Pipeline")

    assert completed_pos != -1
    assert divider_pos != -1
    assert task_pos != -1
    # Task 7 must now appear before the divider and before the Active pipeline
    assert completed_pos < task_pos < divider_pos < active_pos

    # Verify Status line has commit SHA, task_id, and completion status
    assert f"- **Status**: `[x] COMPLETED & MERGED` (`commit abcdef1`, `{task_id}`)" in text
    assert "- **Objective**: Automatically parse merged task metadata upon atomic promotion and update TODO.md and roadmap." in text


def test_roadmap_update_idempotency(tmp_path, sample_roadmap_content):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(sample_roadmap_content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    task_id = "tsk_eva_37eceb12e1b8"
    commit_sha = "abcdef1234567890abcdef1234567890abcdef12"

    res1 = engine.update_roadmap(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
    )
    assert res1 is True

    res2 = engine.update_roadmap(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
    )
    assert res2 is False


def test_roadmap_update_new_task_appends(tmp_path, sample_roadmap_content):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(sample_roadmap_content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    task_id = "tsk_eva_unlisted"
    commit_sha = "7777777666666"

    updated = engine.update_roadmap(
        task_id=task_id,
        commit_sha=commit_sha,
        title="Unlisted Critical Hotfix",
        objective="Fix memory leak in background worker.",
    )
    assert updated is True

    text = roadmap_file.read_text(encoding="utf-8")
    assert "### Unlisted Critical Hotfix" in text
    assert f"- **Status**: `[x] COMPLETED & MERGED` (`commit 7777777`, `{task_id}`)" in text
    assert "- **Objective**: Fix memory leak in background worker." in text


def test_sync_task_completion_wrapper(tmp_path, sample_todo_content, sample_roadmap_content):
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(sample_todo_content, encoding="utf-8")

    docs_dir = tmp_path / "docs" / "architecture"
    docs_dir.mkdir(parents=True, exist_ok=True)
    roadmap_file = docs_dir / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(sample_roadmap_content, encoding="utf-8")

    task_record = {
        "id": "tsk_eva_37eceb12e1b8",
        "envelope": {
            "title": "Autonomous TODO and Roadmap State Machine Sync Engine",
            "description": "Atomically parse merged task metadata and update markdown files.",
            "repo": str(tmp_path),
        },
        "result": {
            "result_sha": "fedcba9876543210fedcba9876543210fedcba98",
        },
    }

    result = sync_task_completion(
        repo_path=tmp_path,
        task=task_record,
    )

    assert result["todo_updated"] is True
    assert result["roadmap_updated"] is True

    todo_text = todo_file.read_text(encoding="utf-8")
    assert "commit fedcba9" in todo_text
    assert "tsk_eva_37eceb12e1b8" in todo_text

    roadmap_text = roadmap_file.read_text(encoding="utf-8")
    assert "commit fedcba9" in roadmap_text
    assert "tsk_eva_37eceb12e1b8" in roadmap_text


@patch("alpha_protocol.task.ReviewAttestation.verify")
@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.Path.exists")
def test_cmd_merge_triggers_todo_and_roadmap_sync(
    mock_exists, mock_run, mock_verify, tmp_path, monkeypatch
):
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "dummy_secret")
    mock_verify.return_value = True

    # Setup TODO.md and NEXT_PHASE_ROADMAP.md in repo
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(
        "# TODO\n\n### Active / In-Progress\n\n- [ ] Autonomous TODO and Roadmap State Machine Sync Engine.\n",
        encoding="utf-8",
    )

    docs_dir = tmp_path / "docs" / "architecture"
    docs_dir.mkdir(parents=True, exist_ok=True)
    roadmap_file = docs_dir / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(
        "# Roadmap\n\n## Completed & Merged Milestones (September 2026)\n\n---\n\n## Active Parallel Development Pipeline (Current)\n\n### Task 7: Autonomous TODO and Roadmap State Machine Sync Engine\n- **Objective**: Automate sync.\n",
        encoding="utf-8",
    )

    evidence = {"test_metric": 10}
    from alpha_protocol.task import ReviewAttestation

    ev_digest = ReviewAttestation.compute_evidence_digest(evidence)
    result_sha = "abc1234567890abcdef1234567890abcdef12345"

    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "tsk_eva_37eceb12e1b8",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_sync",
        "worktree_path": str(tmp_path / "worktree"),
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": result_sha,
            "evidence": evidence,
            "senior_review": {
                "approved": True,
                "pro_verdict": "APPROVE",
                "opus_verdict": "FINAL_APPROVAL",
                "attestation": {
                    "schema_version": "2.0",
                    "task_id": "tsk_eva_37eceb12e1b8",
                    "attempt_id": "att_1",
                    "base_commit": "b" * 40,
                    "result_sha": result_sha,
                    "tree_digest": "c" * 40,
                    "pro_verdict": "APPROVE",
                    "opus_verdict": "FINAL_APPROVAL",
                    "approved": True,
                    "evidence_digest": ev_digest,
                    "reviewed_at": time.time(),
                    "issued_at": time.time(),
                    "expires_at": time.time() + 3600,
                    "nonce": "n_test_sync",
                    "executor_id": "exec_1",
                    "key_id": "alpha_test_key",
                    "reviewer_id": "SYSTEM_SENIOR_REVIEW_ENGINE",
                    "signature": "f" * 64,
                },
            },
        },
        "envelope": {
            "title": "Autonomous TODO and Roadmap State Machine Sync Engine",
            "description": "Automate sync upon merge.",
            "repo": str(tmp_path),
            "base_commit": "b" * 40,
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }

    def mock_exists_side_effect(*args, **kwargs):
        return any("worktree" in str(arg) for arg in args) if args else False

    mock_exists.side_effect = mock_exists_side_effect

    def mock_run_side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[1] == "rev-parse":
            if "^{tree}" in cmd[2]:
                return MagicMock(returncode=0, stdout="c" * 40 + "\n")
            return MagicMock(returncode=0, stdout=result_sha + "\n")
        return MagicMock(returncode=0, stdout="Fast-forward\n")

    mock_run.side_effect = mock_run_side_effect

    args = MagicMock(task_id="tsk_eva_37eceb12e1b8", json=False, skip_senior_review=False)
    with patch("alpha_core.triage_cli.advance_checkout"):
        exit_code = cmd_merge(args, queue)

    assert exit_code == 0

    # Verify both TODO.md and NEXT_PHASE_ROADMAP.md were updated during merge
    todo_text = todo_file.read_text(encoding="utf-8")
    assert "- [x]" in todo_text
    assert "abc1234" in todo_text
    assert "tsk_eva_37eceb12e1b8" in todo_text

    roadmap_text = roadmap_file.read_text(encoding="utf-8")
    assert "[x] COMPLETED & MERGED" in roadmap_text
    assert "abc1234" in roadmap_text
    assert "tsk_eva_37eceb12e1b8" in roadmap_text


def test_todo_update_dash_in_progress_marker(tmp_path):
    todo_file = tmp_path / "TODO.md"
    content = """# TODO
### Active
- [-] Active in-progress task (`tsk_eva_in_prog001`).
"""
    todo_file.write_text(content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, todo_path=todo_file)
    updated = engine.update_todo(
        task_id="tsk_eva_in_prog001",
        commit_sha="abcdef1234567890",
        title="Active in-progress task",
    )
    assert updated is True

    text = todo_file.read_text(encoding="utf-8")
    assert "- [x] Active in-progress task (`commit abcdef1`, `tsk_eva_in_prog001`)." in text
    assert "- [-]" not in text


def test_roadmap_migration_with_preceding_divider(tmp_path):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    content = """# Roadmap Frontmatter

Top level notes.

---

## Completed & Merged Milestones (September 2026)

### Old Task
- **Status**: `[x] COMPLETED & MERGED` (`commit 1111111`, `tsk_old`)
- **Objective**: Previous work.

---

## Active Parallel Development Pipeline (Current)

### Active Feature
- **Task Title**: Active Feature
- **Objective**: Implement active feature.
"""
    roadmap_file.write_text(content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    updated = engine.update_roadmap(
        task_id="tsk_eva_active001",
        commit_sha="9999999888888888",
        title="Active Feature",
        objective="Implement active feature.",
    )
    assert updated is True

    text = roadmap_file.read_text(encoding="utf-8")
    completed_pos = text.find("## Completed & Merged Milestones")
    active_feature_pos = text.find("### Active Feature")
    active_pipeline_pos = text.find("## Active Parallel Development Pipeline")

    assert completed_pos != -1
    assert active_feature_pos != -1
    assert active_pipeline_pos != -1
    # Must be placed under Completed, before Active pipeline
    assert completed_pos < active_feature_pos < active_pipeline_pos
    assert "`commit 9999999`, `tsk_eva_active001`" in text


def test_sync_task_completion_with_objective_only(tmp_path):
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(
        "# TODO\n\n### Implemented foundation\n\n- [ ] Task Objective Only\n",
        encoding="utf-8",
    )

    docs_dir = tmp_path / "docs" / "architecture"
    docs_dir.mkdir(parents=True, exist_ok=True)
    roadmap_file = docs_dir / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(
        "# Roadmap\n\n## Completed & Merged Milestones\n\n---\n\n## Active\n\n### Task Objective Only\n- **Objective**: Task Objective Only\n",
        encoding="utf-8",
    )

    task_record = {
        "id": "tsk_eva_obj_only_123",
        "envelope": {
            "objective": "Task Objective Only",
            "repo": str(tmp_path),
        },
        "result": {
            "result_sha": "3333333444444444333333344444444433333334",
        },
    }

    result = sync_task_completion(
        repo_path=tmp_path,
        task=task_record,
    )
    assert result["todo_updated"] is True
    assert result["roadmap_updated"] is True

    todo_text = todo_file.read_text(encoding="utf-8")
    assert "- [x] Task Objective Only (`commit 3333333`, `tsk_eva_obj_only_123`)." in todo_text

    roadmap_text = roadmap_file.read_text(encoding="utf-8")
    assert "tsk_eva_obj_only_123" in roadmap_text
    assert "3333333" in roadmap_text


def test_todo_sync_creates_files_when_nonexistent(tmp_path):
    todo_file = tmp_path / "TODO.md"
    roadmap_file = tmp_path / "docs" / "architecture" / "NEXT_PHASE_ROADMAP.md"

    engine = TodoSyncEngine(
        repo_path=tmp_path,
        todo_path=todo_file,
        roadmap_path=roadmap_file,
    )
    result = engine.sync(
        task_id="tsk_eva_fresh_init",
        commit_sha="abcdef1234567890",
        title="Fresh Initialize Engine",
        objective="Verify initialization from nonexistent files.",
    )

    assert result["todo_updated"] is True
    assert result["roadmap_updated"] is True
    assert todo_file.exists()
    assert roadmap_file.exists()

    todo_text = todo_file.read_text(encoding="utf-8")
    assert "tsk_eva_fresh_init" in todo_text
    assert "abcdef1" in todo_text

    roadmap_text = roadmap_file.read_text(encoding="utf-8")
    assert "tsk_eva_fresh_init" in roadmap_text
    assert "COMPLETED & MERGED" in roadmap_text


def test_todo_sync_special_characters_in_title(tmp_path, sample_todo_content, sample_roadmap_content):
    todo_file = tmp_path / "TODO.md"
    todo_file.write_text(sample_todo_content, encoding="utf-8")

    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    roadmap_file.write_text(sample_roadmap_content, encoding="utf-8")

    engine = TodoSyncEngine(
        repo_path=tmp_path,
        todo_path=todo_file,
        roadmap_path=roadmap_file,
    )
    result = engine.sync(
        task_id="tsk_eva_special_chars",
        commit_sha="9876543210fedcba",
        title="[Fix] (P0) *critical* feature (v1.0.0+beta)?",
        objective="Handling regex metacharacters cleanly.",
    )

    assert result["todo_updated"] is True
    assert result["roadmap_updated"] is True

    todo_text = todo_file.read_text(encoding="utf-8")
    assert "tsk_eva_special_chars" in todo_text
    assert "9876543" in todo_text

    roadmap_text = roadmap_file.read_text(encoding="utf-8")
    assert "tsk_eva_special_chars" in roadmap_text
    assert "9876543" in roadmap_text


def test_atomic_write_cleans_up_on_failure(tmp_path):
    target_file = tmp_path / "test_target.md"

    from alpha_core.automation.todo_sync import _atomic_write_file

    with patch("os.replace", side_effect=OSError("Disk write error")):
        with pytest.raises(OSError, match="Disk write error"):
            _atomic_write_file(target_file, "Some content")

    # Assert no lingering temp files in directory
    lingering_tmp = list(tmp_path.glob(".tmp_*"))
    assert len(lingering_tmp) == 0


def test_roadmap_migration_preserves_task_metadata_and_custom_properties(tmp_path):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    content = """# Roadmap

## Completed & Merged Milestones
### Task 1: Foundation
- **Status**: `[x] COMPLETED & MERGED` (`commit 0000000`, `tsk_init`)
- **Objective**: Base setup.

---

## Active Parallel Development Pipeline

### Task 7: Autonomous TODO and Roadmap State Machine Sync Engine
- **Task Title**: Implement Autonomous TODO and Roadmap Synchronization Engine
- **Objective**: Automatically parse merged task metadata.
- **Allowed Scope**: `alpha_core/automation/`, `alpha_core/triage_cli.py`
- **Acceptance Criteria**: Passing unit tests verifying markdown parsing.
- **Notes**: Custom developer notes that must never be deleted.
- **Review History**: Approved in round 2.

### Task 8: Parallel Worker Dispatcher Daemon
- **Task Title**: Implement Parallel Worker
"""
    roadmap_file.write_text(content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    updated = engine.update_roadmap(
        task_id="tsk_eva_37eceb12e1b8",
        commit_sha="fedcba9876543210",
        title="Autonomous TODO and Roadmap State Machine Sync Engine",
        objective="Automatically parse merged task metadata upon atomic promotion.",
    )
    assert updated is True

    text = roadmap_file.read_text(encoding="utf-8")

    # Verify task migrated to completed
    assert text.find("## Completed") < text.find("### Task 7") < text.find("---") < text.find("## Active")
    # Verify status line updated
    assert "- **Status**: `[x] COMPLETED & MERGED` (`commit fedcba9`, `tsk_eva_37eceb12e1b8`)" in text
    # Verify objective updated
    assert "- **Objective**: Automatically parse merged task metadata upon atomic promotion." in text
    # Verify ALL original properties and custom notes are strictly preserved
    assert "- **Task Title**: Implement Autonomous TODO and Roadmap Synchronization Engine" in text
    assert "- **Allowed Scope**: `alpha_core/automation/`, `alpha_core/triage_cli.py`" in text
    assert "- **Acceptance Criteria**: Passing unit tests verifying markdown parsing." in text
    assert "- **Notes**: Custom developer notes that must never be deleted." in text
    assert "- **Review History**: Approved in round 2." in text
    # Verify Task 8 remains in active
    assert "### Task 8: Parallel Worker Dispatcher Daemon" in text


def test_roadmap_in_place_update_preserves_trailing_divider_and_sections(tmp_path):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    content = """# Roadmap

## Completed & Merged Milestones (September 2026)

### Task 6: Client Portal API & Frontend
- **Status**: `[x] COMPLETED & MERGED` (`commit 5599d81`, `tsk_eva_3d9c0ffc2606`)
- **Objective**: Implemented Amazon-style client tracking portal UI.
- **Custom Detail**: Detailed portal specs.

---

## Active Parallel Development Pipeline (Current)

### Task 7: Autonomous TODO Sync
- **Objective**: Ongoing work.
"""
    roadmap_file.write_text(content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    # Update Task 6 in place with new commit SHA
    updated = engine.update_roadmap(
        task_id="tsk_eva_3d9c0ffc2606",
        commit_sha="6666666777777777",
        title="Client Portal API & Frontend",
    )
    assert updated is True

    text = roadmap_file.read_text(encoding="utf-8")
    assert "- **Status**: `[x] COMPLETED & MERGED` (`commit 6666666`, `tsk_eva_3d9c0ffc2606`)" in text
    assert "- **Objective**: Implemented Amazon-style client tracking portal UI." in text
    assert "- **Custom Detail**: Detailed portal specs." in text
    # Ensure delimiter and active pipeline headers are NOT deleted
    assert "---" in text
    assert "## Active Parallel Development Pipeline (Current)" in text
    assert "### Task 7: Autonomous TODO Sync" in text


def test_roadmap_migrating_last_task_preserves_trailing_divider_and_execution_handoff(tmp_path):
    roadmap_file = tmp_path / "NEXT_PHASE_ROADMAP.md"
    content = """# Roadmap

## Completed & Merged Milestones

### Task 1: Worker Execution Adapters
- **Status**: `[x] COMPLETED & MERGED` (`commit 1111111`, `tsk_1`)
- **Objective**: Worker adapters.

---

## Active Parallel Development Pipeline (Current)

### Task 9: Async Redis Rate Limiter for FastAPI Endpoints
- **Task Title**: Evaluate and implement open-source Python Redis rate limiter
- **Objective**: Implement robust token-bucket rate limiting on public endpoints.
- **Allowed Scope**: `alpha_core/api/rate_limiter.py`
- **Acceptance Criteria**: Unit tests pass cleanly.

---

## Execution Handoff

Tasks are admitted into the alpha_core triage queue and executed via autonomous pipeline:
1. alpha_core.triage_cli review <task_id>
2. alpha_core.triage_cli merge <task_id>
"""
    roadmap_file.write_text(content, encoding="utf-8")

    engine = TodoSyncEngine(repo_path=tmp_path, roadmap_path=roadmap_file)
    updated = engine.update_roadmap(
        task_id="tsk_eva_5fb3a94658b7",
        commit_sha="9999999000000000",
        title="Async Redis Rate Limiter for FastAPI Endpoints",
    )
    assert updated is True

    text = roadmap_file.read_text(encoding="utf-8")
    # Verify Task 9 moved to Completed
    assert text.find("## Completed") < text.find("### Task 9") < text.find("---")
    # Verify Task 9 properties preserved
    assert "- **Task Title**: Evaluate and implement open-source Python Redis rate limiter" in text
    assert "- **Allowed Scope**: `alpha_core/api/rate_limiter.py`" in text
    assert "- **Acceptance Criteria**: Unit tests pass cleanly." in text
    # Verify Execution Handoff and trailing divider are NOT deleted
    assert "## Execution Handoff" in text
    assert "Tasks are admitted into the alpha_core triage queue" in text
    assert "1. alpha_core.triage_cli review <task_id>" in text


