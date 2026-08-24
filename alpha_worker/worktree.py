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
            base_commit,
        ]
        res = subprocess.run(cmd, cwd=str(validated_repo), capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create git worktree: {res.stderr}")

        return worktree_path

    def get_changed_files(self, worktree_path: Path, base_commit: str = "HEAD") -> list[str]:
        """Returns list of modified or untracked files in the worktree."""
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        files = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1])
        return files

    def get_diff_summary(self, worktree_path: Path) -> str:
        """Returns git diff summary."""
        res = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        return res.stdout.strip()

    def commit_changes(self, worktree_path: Path, message: str) -> str | None:
        """Stages all changes and commits them, returning the new commit hash."""
        subprocess.run(["git", "add", "-A"], cwd=str(worktree_path), check=True)
        res = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return None

        rev_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        return rev_res.stdout.strip()

    def remove_worktree(self, repo_path: str, task_id: str) -> None:
        """Safely removes the worktree and prunes git worktree references."""
        validated_repo = self.validate_repo_path(repo_path)
        worktree_path = self.get_worktree_path(task_id)
        if worktree_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=str(validated_repo),
                capture_output=True,
            )
            # Extra cleanup if directory lingers
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)

        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(validated_repo),
            capture_output=True,
        )
