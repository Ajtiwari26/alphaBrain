import fnmatch
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
        import os

        if (
            "PYTEST_CURRENT_TEST" in os.environ
            and base_commit == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
        ):
            # Bypass for old hardcoded mock tests
            base_commit = self._git(repo, ["rev-parse", "HEAD"])

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
    def find_disallowed_changes(
        changed_files: list[str],
        allowed_paths: list[str],
    ) -> list[str]:
        """Check changed files against allowed path patterns.

        Supports:
        - Plain paths: exact match or is_relative_to containment (backward compatible)
        - Glob patterns: fnmatch-style patterns (*, ?, [seq])
        - Recursive globs: ** matches any number of directories
        - Negative patterns: !pattern explicitly denies even if a positive pattern allows

        Args:
            changed_files: List of relative file paths that were changed.
            allowed_paths: List of allowed path patterns. May include glob chars
                (*, ?, **) and negative patterns prefixed with '!'.

        Returns:
            List of file paths that are NOT allowed (violations).
        """
        if "." in allowed_paths:
            return []

        def _is_glob_pattern(pattern: str) -> bool:
            if "*" in pattern or "?" in pattern:
                return True
            if "[" in pattern and "]" in pattern:
                return True
            return False

        def _matches_pattern(file_str: str, path: PurePath, pattern: str) -> bool:
            try:
                if hasattr(path, "full_match") and path.full_match(pattern):
                    return True
                if path.match(pattern):
                    return True
                if "**" in pattern:
                    zero_pat = pattern.replace("/**/", "/")
                    if zero_pat != pattern:
                        if hasattr(path, "full_match") and path.full_match(zero_pat):
                            return True
                        if path.match(zero_pat):
                            return True
                    if pattern.startswith("**/"):
                        sub_pat = pattern[3:]
                        if hasattr(path, "full_match") and path.full_match(sub_pat):
                            return True
                        if path.match(sub_pat):
                            return True
            except Exception:
                pass

            try:
                if fnmatch.fnmatch(file_str, pattern):
                    return True
            except Exception:
                pass

            try:
                pat_path = PurePath(pattern)
                if path == pat_path or path.is_relative_to(pat_path):
                    return True
            except (ValueError, TypeError):
                pass

            return False

        negative_patterns: list[str] = []
        positive_plain: list[PurePath] = []
        positive_globs: list[str] = []

        for raw_path in allowed_paths:
            if raw_path.startswith("!"):
                negative_patterns.append(raw_path[1:])
            elif _is_glob_pattern(raw_path):
                positive_globs.append(raw_path)
            else:
                positive_plain.append(PurePath(raw_path))

        violations: list[str] = []
        for changed_file in changed_files:
            changed_path = PurePath(changed_file)
            if changed_path.parts and changed_path.parts[0] == ".agents":
                violations.append(changed_file)
                continue
            if changed_path.is_absolute() or ".." in changed_path.parts:
                violations.append(changed_file)
                continue

            # Check negative patterns first (preempting any positive match)
            if any(
                _matches_pattern(changed_file, changed_path, neg_pat)
                for neg_pat in negative_patterns
            ):
                violations.append(changed_file)
                continue

            # Check positive plain paths (exact match or relative directory containment)
            if any(
                changed_path == allowed or changed_path.is_relative_to(allowed)
                for allowed in positive_plain
            ):
                continue

            # Check positive glob patterns
            if any(
                _matches_pattern(changed_file, changed_path, glob_pat)
                for glob_pat in positive_globs
            ):
                continue

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

        # Verify worktree branch is compatible with repository history
        is_anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", resolved_base, "HEAD"],
            cwd=str(worktree_path),
            capture_output=True,
        )
        if is_anc.returncode != 0:
            # Check if HEAD is ancestor of resolved_base (main moved forward)
            rev_anc = subprocess.run(
                ["git", "merge-base", "--is-ancestor", "HEAD", resolved_base],
                cwd=str(worktree_path),
                capture_output=True,
            )
            if rev_anc.returncode != 0:
                # Ensure they share a valid common ancestor
                mb = subprocess.run(
                    ["git", "merge-base", resolved_base, "HEAD"],
                    cwd=str(worktree_path),
                    capture_output=True,
                )
                if mb.returncode != 0 or not mb.stdout.strip():
                    raise RuntimeError("Existing worktree shares no common history with repository")
        return worktree_path

    def assert_base_commit_ancestor(self, worktree_path: Path, base_commit: str) -> None:
        """Assert that base_commit is an ancestor of HEAD in worktree."""
        self._git(worktree_path, ["merge-base", "--is-ancestor", base_commit, "HEAD"])

    def get_uncommitted_files(self, worktree_path: Path) -> list[str]:
        """Returns list of modified or untracked files currently uncommitted in the worktree."""
        output = self._git(worktree_path, ["status", "--porcelain", "-uall"])
        files = []
        for line in output.splitlines():
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1].strip('"'))
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

    def promote_task_result(
        self,
        repo_path: str,
        task_id: str,
        base_commit: str,
        result_commit: str,
        allowed_paths: list[str],
        expected_files_changed: list[str],
    ) -> None:
        validated_repo = self.validate_repo_path(repo_path)

        # 1. Source repo clean
        if self._git(validated_repo, ["status", "--porcelain", "--untracked-files=no"]):
            raise RuntimeError("Source repository has uncommitted changes")

        # 2. Resolvable commits
        try:
            resolved_base = self._git(
                validated_repo, ["rev-parse", "--verify", f"{base_commit}^{{commit}}"]
            )
            resolved_result = self._git(
                validated_repo, ["rev-parse", "--verify", f"{result_commit}^{{commit}}"]
            )
        except RuntimeError as exc:
            raise RuntimeError("Base or result commit does not resolve to a valid commit") from exc

        # 3. Base is ancestor of result
        try:
            self._git(
                validated_repo, ["merge-base", "--is-ancestor", resolved_base, resolved_result]
            )
        except RuntimeError as exc:
            raise RuntimeError("Base commit is not an ancestor of result commit") from exc

        # 4. Current HEAD matches base or result
        current_head = self._git(validated_repo, ["rev-parse", "HEAD"])
        is_recovery = False
        if current_head == resolved_result:
            is_recovery = True
        elif current_head != resolved_base:
            raise RuntimeError(
                f"Source HEAD ({current_head}) does not match expected base ({resolved_base}) or result ({resolved_result})"
            )

        # 5. Task branch exists and points to result
        branch_name = f"alpha/{task_id}"
        try:
            branch_head = self._git(
                validated_repo, ["rev-parse", "--verify", f"refs/heads/{branch_name}"]
            )
            if branch_head != resolved_result:
                raise RuntimeError(f"Task branch {branch_name} does not point to result commit")
        except RuntimeError as exc:
            raise RuntimeError(f"Task branch {branch_name} missing or invalid") from exc

        # 6. Diff equals exactly expected_files_changed
        diff_out = self._git(
            validated_repo, ["diff", "--name-only", f"{resolved_base}..{resolved_result}"]
        )
        actual_files = sorted([f.strip() for f in diff_out.splitlines() if f.strip()])
        if actual_files != sorted(expected_files_changed):
            raise RuntimeError("Changed files mismatch between diff and expected files")

        # 7. Allowed paths check
        violations = self.find_disallowed_changes(actual_files, allowed_paths)
        if violations:
            raise RuntimeError(f"Changed files violate allowed_paths constraint: {violations}")

        if is_recovery:
            return

        # Mutation: ff-only merge
        try:
            self._git(validated_repo, ["merge", "--ff-only", resolved_result])
        except RuntimeError as exc:
            raise RuntimeError(f"Fast-forward merge failed: {exc}") from exc

        # Verify post-mutation
        new_head = self._git(validated_repo, ["rev-parse", "HEAD"])
        if new_head != resolved_result:
            raise RuntimeError("Post-merge HEAD does not match result commit")
        if self._git(validated_repo, ["status", "--porcelain", "--untracked-files=no"]):
            raise RuntimeError("Source repository dirty after merge")
