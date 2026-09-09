"""Non-destructive promotion of a clean, checked-out main branch."""

import subprocess


def advance_checkout(repo: str, base: str, result: str) -> None:
    """Advance ref and checkout together; refuse ambiguous or dirty destinations.

    Caller holds the promotion lock. Never use update-ref on a checked-out
    branch: it leaves the index behind and turns old files into staged reverts.
    """

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()

    def clean() -> None:
        git("diff", "--cached", "--quiet", "HEAD", "--")
        git("diff", "--quiet", "HEAD", "--")
        untracked = git("ls-files", "--others", "--exclude-standard", "-z")
        if any(p and not p.startswith(".alphabrain/") for p in untracked.split("\0")):
            raise ValueError("Untracked destination files prevent promotion")

    if git("symbolic-ref", "--quiet", "HEAD") != "refs/heads/main":
        raise ValueError("Promotion destination must have main checked out")
    current = git("rev-parse", "HEAD")
    if current not in (base, result):
        raise ValueError("Destination advanced or diverged; refusing promotion")
    clean()
    git("merge-base", "--is-ancestor", base, result)
    if current != result:
        git("-c", "core.hooksPath=/dev/null", "merge", "--ff-only", "--no-edit", result)
    if git("rev-parse", "HEAD") != result:
        raise ValueError("Destination HEAD does not match approved result")
    if git("write-tree") != git("rev-parse", f"{result}^{{tree}}"):
        raise ValueError("Destination index does not match approved result")
    clean()
