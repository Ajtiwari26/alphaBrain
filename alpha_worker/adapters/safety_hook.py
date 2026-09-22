#!/usr/bin/env python3
"""Fail-closed tool policy. Task shell syntax runs only inside sandbox-exec."""

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

FILE_TOOLS = {"write_to_file", "replace_file_content", "multi_replace_file_content", "delete_file"}
READ_TOOLS = {"view_file", "list_dir", "grep_search", "find_by_name"}
PROTECTED = (".agents", ".gemini", ".git")
AGY_BRAIN_RELATIVE = Path(".gemini/antigravity-ide/brain")


def deny(reason: str) -> dict[str, Any]:
    return {"decision": "deny", "reason": reason}


def scoped_path(value: Any, worktree: Path) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Missing or invalid path")
    path = Path(value)
    path = (path if path.is_absolute() else worktree / path).resolve()
    if not path.is_relative_to(worktree):
        raise ValueError("Path outside assigned worktree")
    return path


def _git_read_paths(worktree: Path) -> tuple[list[Path], list[Path]]:
    """Trust only Git's standard linked-worktree metadata layout, read-only."""
    marker = worktree / ".git"
    if not marker.is_file():
        return [], []
    text = marker.read_text().strip()
    if not text.startswith("gitdir: "):
        raise ValueError("Invalid Git worktree metadata")
    raw = Path(text[len("gitdir: ") :])
    git_dir = (raw if raw.is_absolute() else worktree / raw).resolve(strict=True)
    if git_dir.parent.name != "worktrees":
        raise ValueError("Unsupported Git worktree metadata layout")
    common = git_dir.parent.parent
    if (git_dir / "commondir").read_text().strip() != "../..":
        raise ValueError("Unexpected Git common directory")
    backlink = Path((git_dir / "gitdir").read_text().strip()).resolve()
    if backlink != marker.resolve():
        raise ValueError("Git worktree identity mismatch")
    return [git_dir, common / "objects", common / "refs"], [
        common / name for name in ("config", "HEAD", "packed-refs", "shallow")
    ]


def _is_protected_execution_path(path: Path, worktree: Path) -> bool:
    """Reserve agent/runtime configuration from every model-issued tool call."""
    return any(
        path == worktree / name or path.is_relative_to(worktree / name) for name in PROTECTED
    )


def sandbox_profile(worktree: Path) -> str:
    """Allow code/runtime reads and task-local writes, never shared state."""
    import mimetypes

    worktree = worktree.resolve()
    runtime = [
        Path(p)
        for p in (
            "/System",
            "/usr",
            "/bin",
            "/sbin",
            "/Library/Apple",
            "/Library/Developer/CommandLineTools",
            "/opt/homebrew",
            "/private/etc",
            "/etc",
            "/private/var",
            "/var",
            "/private/tmp",
            "/tmp",
        )
        if Path(p).exists()
    ]
    runtime.append(Path(sys.prefix).resolve())
    cargo_home = Path.home() / ".cargo"
    if cargo_home.is_dir():
        runtime.append(cargo_home.resolve())
    rustup_home = Path.home() / ".rustup"
    if rustup_home.is_dir():
        runtime.append(rustup_home.resolve())
    git_roots, git_files = _git_read_paths(worktree)
    read_roots = [*runtime, *git_roots]
    # getcwd traverses parent directories on macOS. Directory literals do not
    # authorize reading files beneath those parents.
    directory_literals = {Path("/")}
    for root in [worktree, *read_roots, *git_files]:
        directory_literals.update(root.parents)
    file_literals = [
        worktree / ".git",
        *git_files,
        *(Path(p).resolve() for p in mimetypes.knownfiles),
        Path("/dev/null"),
        Path("/dev/urandom"),
        Path("/dev/random"),
    ]

    def rule(action: str, operation: str, selector: str, path: Path) -> str:
        return f"({action} {operation} ({selector} {json.dumps(str(path), ensure_ascii=False)}))"

    def task_scope(operation: str) -> str:
        exclusions = " ".join(
            f"(require-not (subpath {json.dumps(str(worktree / name), ensure_ascii=False)}))"
            for name in PROTECTED
        )
        return (
            f"(allow {operation} (require-all (subpath "
            f"{json.dumps(str(worktree), ensure_ascii=False)}) {exclusions}))"
        )

    return "\n".join(
        [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            '(allow network* (local ip "localhost:*"))',
            '(allow network* (remote ip "localhost:*"))',
            "(deny file-read-data)",
            "(deny file-write*)",
            task_scope("file-read-data"),
            *(rule("allow", "file-read-data", "subpath", p) for p in read_roots),
            *(rule("allow", "file-read-data", "literal", p) for p in sorted(directory_literals)),
            *(rule("allow", "file-read-data", "literal", p) for p in file_literals),
            task_scope("file-write*"),
            rule("allow", "file-write*", "subpath", Path("/private/tmp")),
            rule("allow", "file-write*", "subpath", Path("/tmp")),
            rule("allow", "file-write*", "subpath", Path("/private/var/folders")),
            rule("allow", "file-write*", "subpath", Path("/var/folders")),
            rule("allow", "file-write-data", "literal", Path("/dev/null")),
        ]
    )


def decide(payload: Any, worktree: Path) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("toolCall"), dict):
        return deny("Invalid tool-call object")
    call = payload["toolCall"]
    name, original = call.get("name"), call.get("args")
    if not isinstance(name, str) or not isinstance(original, dict):
        return deny("Invalid tool name or arguments")
    args = original.copy()
    worktree = worktree.resolve(strict=True)
    if not worktree.is_dir():
        return deny("Worktree must be an existing directory")
    try:
        if name in FILE_TOOLS:
            path = scoped_path(args.get("TargetFile") or args.get("AbsolutePath"), worktree)
            if path == worktree or _is_protected_execution_path(path, worktree):
                return deny("Protected execution configuration")
        elif name in READ_TOOLS:
            path = scoped_path(
                args.get("AbsolutePath")
                or args.get("TargetFile")
                or args.get("DirectoryPath")
                or args.get("SearchPath")
                or args.get("SearchDirectory"),
                worktree,
            )
            if _is_protected_execution_path(path, worktree):
                return deny("Protected execution configuration")
        elif name == "run_command":
            cwd = scoped_path(args.get("Cwd"), worktree)
            command = args.get("CommandLine")
            if (
                not cwd.is_dir()
                or not isinstance(command, str)
                or not command.strip()
                or "\x00" in command
            ):
                return deny("Missing or invalid command/CWD")
            if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
                return deny("Required macOS sandbox unavailable")
            # Writable SDK/cache state belongs to this task, not host credentials
            # or the protected project-level agent configuration.
            state = scoped_path(".alphabrain-sandbox", worktree)
            home = scoped_path(str(state / "home"), worktree)
            temp = scoped_path(str(state / "tmp"), worktree)
            for directory in (home, temp):
                directory.mkdir(parents=True, exist_ok=True)
            # Clear inherited credentials and shell startup overrides.
            cargo_bin = Path.home() / ".cargo" / "bin"
            extra_path = f":{cargo_bin}" if cargo_bin.is_dir() else ""
            argv = [
                "/usr/bin/sandbox-exec",
                "-p",
                sandbox_profile(worktree),
                "/usr/bin/env",
                "-i",
                f"PATH={Path(sys.prefix) / 'bin'}:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin{extra_path}",
                f"HOME={home}",
                f"RUSTUP_HOME={Path.home() / '.rustup'}",
                f"CARGO_HOME={Path.home() / '.cargo'}",
                f"TMPDIR={temp}",
                f"TEMP={temp}",
                f"TMP={temp}",
                f"XDG_CACHE_HOME={home / '.cache'}",
                f"XDG_CONFIG_HOME={home / '.config'}",
                "GIT_OPTIONAL_LOCKS=0",
                "PYTHONDONTWRITEBYTECODE=1",
                "/bin/sh",
                "-c",
                command,
            ]
            args["Cwd"] = str(cwd)
            args["CommandLine"] = shlex.join(argv)
        elif name == "call_mcp_tool":
            server = args.get("ServerName")
            if server == "code-review-graph":
                return {"decision": "allow", "overwrite": args}
            return deny("Tool has no containment policy")
        else:
            return deny("Tool has no containment policy")
    except (ValueError, OSError):
        return deny("Invalid or out-of-scope tool path")
    result: dict[str, Any] = {"decision": "allow", "overwrite": args}
    if name == "run_command":
        result["permissionOverrides"] = [f"command({original['CommandLine']})"]
    return result


def main() -> None:
    try:
        worktree = os.environ.get("ALPHA_WORKTREE_PATH")
        result = (
            decide(json.loads(sys.stdin.read()), Path(worktree))
            if worktree
            else deny("Missing ALPHA_WORKTREE_PATH")
        )
    except (ValueError, TypeError, OSError):
        result = deny("Invalid hook request or unavailable worktree")
    # Do not log raw payloads, commands, credentials or model output.
    print(json.dumps(result))


if __name__ == "__main__":
    main()
