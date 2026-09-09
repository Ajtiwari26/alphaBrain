#!/usr/bin/env python3
"""Programmatic safety hook to replace --dangerously-skip-permissions.
Ensures all AGY tool calls are contained within the assigned Git worktree.
"""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        with open("/tmp/safety_hook.log", "a") as f:
            f.write(f"RAW INPUT: {raw_input}\n")
        input_data = json.loads(raw_input)
    except Exception as e:
        with open("/tmp/safety_hook.log", "a") as f:
            f.write(f"EXCEPTION: {e}\n")
        sys.exit(0)
    tool_call = input_data.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    wait_ms = args.get("WaitMsBeforeAsync")
    if isinstance(wait_ms, str) and wait_ms.isdigit():
        args["WaitMsBeforeAsync"] = int(wait_ms)

    for k, v in args.items():
        if isinstance(v, str):
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                args[k] = v[1:-1]

    def respond(payload: dict) -> None:
        out_str = json.dumps(payload)
        with open("/tmp/safety_hook.log", "a") as f:
            f.write(f"OUTPUT: {out_str}\n")
        print(out_str)
        sys.exit(0)

    worktree_path = os.environ.get("ALPHA_WORKTREE_PATH")
    if not worktree_path:
        respond({"decision": "deny", "reason": "Missing ALPHA_WORKTREE_PATH environment variable."})
        sys.exit(0)

    wt_path = Path(worktree_path).resolve()

    # Strictly enforce containment for file modifications
    if tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content", "delete_file"]:
        path = args.get("TargetFile") or args.get("AbsolutePath")
        if not path:
            respond({"decision": "deny", "reason": "Missing TargetFile or AbsolutePath argument"})
            sys.exit(0)
            
        path = path.strip("\"'")
        resolved_path = Path(path).resolve()
        if not resolved_path.is_relative_to(wt_path):
            respond(
                {
                    "decision": "deny",
                    "reason": f"Security Exception: File write path '{path}' is outside the assigned worktree '{wt_path}'",
                }
            )
        if resolved_path.is_relative_to(wt_path / ".agents"):
            respond(
                {
                    "decision": "deny",
                    "reason": f"Security Exception: Modifying the hook configuration file '{path}' is strictly prohibited",
                }
            )

    # Strictly enforce containment for command execution environments
    if tool_name == "run_command":
        cwd = args.get("Cwd")
        if cwd:
            cwd = cwd.strip("\"'")
            resolved_cwd = Path(cwd).resolve()
            if not resolved_cwd.is_relative_to(wt_path):
                respond(
                    {
                        "decision": "deny",
                        "reason": f"Security Exception: Command CWD '{cwd}' is outside the assigned worktree '{wt_path}'",
                    }
                )
                
        # OS-level Sandbox Hardening via macOS sandbox-exec
        cmd = args.get("CommandLine", "")
        if cmd:
            import tempfile
            
            profile = f"""(version 1)
(allow default)
(deny file-write* (subpath "/"))
(allow file-write* (subpath "{wt_path!s}"))
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/tmp"))
(allow file-write* (subpath "/var"))
(allow file-write* (subpath "/dev"))
"""
            fd, profile_path = tempfile.mkstemp(prefix="alpha_sandbox_", suffix=".sb")
            with os.fdopen(fd, 'w') as f:
                f.write(profile)
            
            escaped_cmd = json.dumps(cmd)
            args["CommandLine"] = f"sandbox-exec -f {profile_path} /bin/sh -c {escaped_cmd}"

    # If no checks failed, we programmatically allow the execution and overwrite the args to fix model formatting errors
    respond(
        {
            "decision": "allow",
            "reason": "Worktree containment verified by programmatic hook.",
            "overwrite": args,
            "permissionOverrides": [f"command({args.get('CommandLine', '*')})"],
        }
    )


if __name__ == "__main__":
    main()
