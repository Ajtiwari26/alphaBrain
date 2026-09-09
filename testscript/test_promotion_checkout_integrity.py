"""Real Git regression tests: ref movement must not leave a stale checkout."""

import subprocess

import pytest

from alpha_core.promotion_checkout import advance_checkout


def git(repo, *args, input=None):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def candidate(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    path = tmp_path / "app.txt"
    path.write_text("base\n")
    git(tmp_path, "add", "app.txt")
    git(tmp_path, "commit", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "-b", "candidate")
    path.write_text("candidate\n")
    git(tmp_path, "commit", "-am", "candidate")
    result = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    return tmp_path, base, result


def test_ref_index_and_files_advance_together_and_replay(candidate):
    repo, base, result = candidate
    for _ in range(2):
        advance_checkout(str(repo), base, result)
        assert git(repo, "rev-parse", "HEAD") == result
        assert git(repo, "write-tree") == git(repo, "rev-parse", f"{result}^{{tree}}")
        assert (repo / "app.txt").read_text() == "candidate\n"
        assert git(repo, "status", "--porcelain") == ""


@pytest.mark.parametrize("kind", ["unstaged", "staged", "untracked", "hidden_index"])
def test_dirty_checkout_is_preserved(candidate, kind):
    repo, base, result = candidate
    path = repo / ("new.txt" if kind == "untracked" else "app.txt")
    path.write_text("user work\n")
    if kind in ("staged", "hidden_index"):
        git(repo, "add", "app.txt")
    if kind == "hidden_index":
        path.write_text("base\n")
    before = (git(repo, "status", "--porcelain"), git(repo, "write-tree"), path.read_bytes())
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        advance_checkout(str(repo), base, result)
    assert git(repo, "rev-parse", "HEAD") == base
    assert before == (
        git(repo, "status", "--porcelain"),
        git(repo, "write-tree"),
        path.read_bytes(),
    )


@pytest.mark.parametrize("diverged", [False, True])
def test_advanced_or_divergent_main_never_rewinds(candidate, diverged):
    repo, base, result = candidate
    if not diverged:
        git(repo, "merge", "--ff-only", result)
    (repo / "later.txt").write_text("later work\n")
    git(repo, "add", "later.txt")
    git(repo, "commit", "-m", "later")
    later = git(repo, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="advanced or diverged"):
        advance_checkout(str(repo), base, result)
    assert git(repo, "rev-parse", "HEAD") == later
    assert (repo / "later.txt").read_text() == "later work\n"


def test_legacy_ref_only_promotion_fails_without_discarding_files(candidate):
    repo, base, result = candidate
    git(repo, "update-ref", "refs/heads/main", result, base)
    with pytest.raises(subprocess.CalledProcessError):
        advance_checkout(str(repo), base, result)
    assert (repo / "app.txt").read_text() == "base\n"
    assert git(repo, "write-tree") != git(repo, "rev-parse", f"{result}^{{tree}}")


def test_other_checked_out_branch_is_not_switched(candidate):
    repo, base, result = candidate
    git(repo, "checkout", "candidate")
    with pytest.raises(ValueError, match="main checked out"):
        advance_checkout(str(repo), base, result)
    assert git(repo, "branch", "--show-current") == "candidate"
