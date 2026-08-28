import re
import shutil
import subprocess
from pathlib import Path, PurePath

from alpha_core.config import settings


class WorktreeManager:
    """Manages ephemeral, isolated Git worktrees for safe task execution."""

    TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

    def __init__(self, base_worktree_dir: Path | None = None):
        self.base_dir = (base_worktree_dir or settings.WORKTREE_BASE_DIR).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_worktree_path(self, task_id: str) -> Path:
        self.validate_task_id(task_id)
        worktree_path = (self.base_dir / task_id).resolve()
        if not worktree_path.is_relative_to(self.base_dir):
            raise ValueError("Worktree path escapes configured base directory")
        return worktree_path

    @classmethod
    def validate_task_id(cls, task_id: str) -> None:
        if not cls.TASK_ID_PATTERN.fullmatch(task_id):
            raise ValueError("Invalid task ID")

    @staticmethod
    def validate_repo_path(repo_path: str) -> Path:
        path = Path(repo_path).expanduser().resolve()
        allowed_roots = tuple(root.expanduser().resolve() for root in settings.ALLOWED_REPO_ROOTS)
        if not allowed_roots:
            raise ValueError("No repository roots are configured")
        if not any(path == root or path.is_relative_to(root) for root in allowed_roots):
            raise ValueError("Repository path is outside allowed roots")
        if not path.is_dir():
            raise ValueError("Repository path does not exist")
        git_check = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
        )
        if git_check.returncode != 0 or git_check.stdout.strip() != "true":
            raise ValueError("Repository path is not a Git worktree")
        return path

    @staticmethod
    def _git(repo: Path, args: list[str]) -> str:
        result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
        return result.stdout.strip()

    def validate_clean_base_commit(self, repo: Path, base_commit: str) -> str:
        """Require clean source repository and resolve exact immutable task base commit."""
        if self._git(repo, ["status", "--porcelain"]):
            raise RuntimeError("Repository has uncommitted changes; refusing task worktree")
        return self._git(repo, ["rev-parse", "--verify", f"{base_commit}^{{commit}}"])

    def _worktree_bytes(self) -> int:
        total = 0
        for path in self.base_dir.rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        return total

    def enforce_disk_quota(self) -> None:
        used_bytes = self._worktree_bytes()
        max_bytes = int(settings.WORKTREE_MAX_DISK_GB * 1024**3)
        free_bytes = shutil.disk_usage(self.base_dir).free
        min_free_bytes = int(settings.WORKTREE_MIN_FREE_GB * 1024**3)
        if used_bytes >= max_bytes:
            raise RuntimeError("Worktree disk quota reached; explicit cleanup required")
        if free_bytes < min_free_bytes:
            raise RuntimeError("Insufficient free disk for task worktree")

    @staticmethod
    def find_disallowed_changes(changed_files: list[str], allowed_paths: list[str]) -> list[str]:
        if "." in allowed_paths:
            return []
        allowed = [PurePath(path) for path in allowed_paths]
        violations: list[str] = []
        for changed_file in changed_files:
            changed_path = PurePath(changed_file)
            if changed_path.is_absolute() or ".." in changed_path.parts:
                violations.append(changed_file)
                continue
            if not any(
                changed_path == allowed_path or changed_path.is_relative_to(allowed_path)
                for allowed_path in allowed
            ):
                violations.append(changed_file)
        return violations

    def create_worktree(
        self,
        repo_path: str,
        task_id: str,
        base_commit: str = "HEAD",
    ) -> Path:
        """Creates an isolated git worktree for a specific task."""
        validated_repo = self.validate_repo_path(repo_path)
        resolved_base = self.validate_clean_base_commit(validated_repo, base_commit)
        self.enforce_disk_quota()
        worktree_path = self.get_worktree_path(task_id)
        if worktree_path.exists():
            raise RuntimeError(f"Worktree already exists for task {task_id}")

        branch_name = f"alpha/{task_id}"

        branch_check = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=str(validated_repo),
        )
        if branch_check.returncode == 0:
            raise RuntimeError(f"Task branch already exists: {branch_name}")

        cmd = [
            "git",
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            resolved_base,
        ]
        res = subprocess.run(cmd, cwd=str(validated_repo), capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create git worktree: {res.stderr}")

        return worktree_path

    def create_or_resume_worktree(
        self,
        repo_path: str,
        task_id: str,
        base_commit: str = "HEAD",
    ) -> Path:
        """Reuse only matching task worktree; otherwise create isolated worktree."""
        worktree_path = self.get_worktree_path(task_id)
        if not worktree_path.exists():
            branch_name = f"alpha/{task_id}"
            validated_repo = self.validate_repo_path(repo_path)

            # Always prune stale worktree references
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(validated_repo),
                capture_output=True,
            )

            branch_check = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
                cwd=str(validated_repo),
            )

            if branch_check.returncode == 0:
                # Branch exists but worktree directory is missing; reattach
                cmd = ["git", "worktree", "add", str(worktree_path), branch_name]
                res = subprocess.run(cmd, cwd=str(validated_repo), capture_output=True, text=True)
                if res.returncode != 0:
                    raise RuntimeError(
                        f"Failed to reattach worktree to existing branch: {res.stderr}"
                    )
                return worktree_path
            else:
                return self.create_worktree(repo_path, task_id, base_commit)

        validated_repo = self.validate_repo_path(repo_path)
        resolved_base = self._git(
            validated_repo, ["rev-parse", "--verify", f"{base_commit}^{{commit}}"]
        )
        expected_branch = f"alpha/{task_id}"
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        if branch.returncode != 0 or branch.stdout.strip() != expected_branch:
            raise RuntimeError("Existing worktree does not match task branch; refusing resume")
        self._git(worktree_path, ["merge-base", "--is-ancestor", resolved_base, "HEAD"])
        return worktree_path

    def assert_base_commit_ancestor(self, worktree_path: Path, base_commit: str) -> None:
        """Assert that base_commit is an ancestor of HEAD in worktree."""
        self._git(worktree_path, ["merge-base", "--is-ancestor", base_commit, "HEAD"])

    def get_uncommitted_files(self, worktree_path: Path) -> list[str]:
        """Returns list of modified or untracked files currently uncommitted in the worktree."""
        output = self._git(worktree_path, ["status", "--porcelain"])
        files = []
        for line in output.splitlines():
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1])
        return files

    def get_changed_files(self, worktree_path: Path, base_commit: str = "HEAD") -> list[str]:
        """Returns list of files changed between base_commit and worktree HEAD."""
        self.assert_base_commit_ancestor(worktree_path, base_commit)
        output = self._git(worktree_path, ["diff", "--name-only", f"{base_commit}..HEAD"])
        return [f.strip() for f in output.splitlines() if f.strip()]

    def get_diff_summary(self, worktree_path: Path, base_commit: str = "HEAD") -> str:
        """Returns git diff summary against base_commit."""
        self.assert_base_commit_ancestor(worktree_path, base_commit)
        return self._git(worktree_path, ["diff", "--stat", f"{base_commit}..HEAD"])

    def get_head_commit(self, worktree_path: Path) -> str:
        """Returns the full commit hash of HEAD in the worktree."""
        return self._git(worktree_path, ["rev-parse", "HEAD"])

    def commit_changes(self, worktree_path: Path, message: str) -> str:
        """Stages all changes and commits them, returning the new commit hash."""
        self._git(worktree_path, ["add", "-A"])
        self._git(worktree_path, ["commit", "-m", message])
        return self.get_head_commit(worktree_path)

    def remove_worktree(self, repo_path: str, task_id: str) -> None:
        """Remove only clean worktree; preserve task branch and never force-delete evidence."""
        validated_repo = self.validate_repo_path(repo_path)
        worktree_path = self.get_worktree_path(task_id)
        if worktree_path.exists():
            if self._git(worktree_path, ["status", "--porcelain"]):
                raise RuntimeError("Worktree has uncommitted changes; preserving for inspection")
            result = subprocess.run(
                ["git", "worktree", "remove", str(worktree_path)],
                cwd=str(validated_repo),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Failed to remove clean worktree")

        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(validated_repo),
            capture_output=True,
        )
