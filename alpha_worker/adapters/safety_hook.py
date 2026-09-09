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


def sandbox_profile(worktree: Path) -> str:
    def subpath(path: Path | str) -> str:
        return f"(subpath {json.dumps(str(path), ensure_ascii=False)})"

    # Read-only runtimes; no broad home, /var or /tmp grants.
    runtime = ["/System", "/usr", "/bin", "/sbin", "/Library/Apple", "/opt/homebrew"]
    runtime.append(str(Path(sys.prefix).resolve()))
    return "\n".join(
        [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-read-data)",
            "(deny file-write*)",
            '(allow file-read-data (literal "/"))',
            f"(allow file-read-data {subpath(worktree)})",
            *(f"(allow file-read-data {subpath(path)})" for path in runtime),
            # Python's mimetypes module checks this one public database.
            '(allow file-read-data (literal "/etc/mime.types") (literal "/private/etc/mime.types"))',
            '(allow file-read-data (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))',
            f"(allow file-write* {subpath(worktree)})",
            '(allow file-write-data (literal "/dev/null"))',
            f"(deny file-write-unlink (literal {json.dumps(str(worktree))}))",
            *(f"(deny file-write* {subpath(worktree / name)})" for name in PROTECTED),
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
            if path == worktree or any(path.is_relative_to(worktree / p) for p in PROTECTED):
                return deny("Protected execution configuration")
        elif name in READ_TOOLS:
            scoped_path(
                args.get("AbsolutePath")
                or args.get("TargetFile")
                or args.get("DirectoryPath")
                or args.get("SearchPath")
                or args.get("SearchDirectory"),
                worktree,
            )
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
            # Clear inherited credentials and shell startup overrides.
            argv = [
                "/usr/bin/sandbox-exec",
                "-p",
                sandbox_profile(worktree),
                "/usr/bin/env",
                "-i",
                "PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
                f"HOME={worktree}",
                f"TMPDIR={worktree}",
                "PYTHONDONTWRITEBYTECODE=1",
                "/bin/sh",
                "-c",
                command,
            ]
            args["Cwd"] = str(cwd)
            args["CommandLine"] = shlex.join(argv)
        else:
            return deny("Tool has no containment policy")
    except (ValueError, OSError):
        return deny("Invalid or out-of-scope tool path")
    result: dict[str, Any] = {"decision": "allow", "overwrite": args}
    if name == "run_command":
        result["permissionOverrides"] = [f"command({args['CommandLine']})"]
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
