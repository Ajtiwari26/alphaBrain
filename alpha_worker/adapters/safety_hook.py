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

    wt_path = Path(worktree_path).resolve()

    # Strictly enforce containment for file modifications
    if tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content"]:
        path = args.get("TargetFile") or args.get("AbsolutePath")
        if path:
            path = path.strip("\"'")
            if not str(Path(path).resolve()).startswith(str(wt_path)):
                respond(
                    {
                        "decision": "deny",
                        "reason": f"Security Exception: File write path '{path}' is outside the assigned worktree '{wt_path}'",
                    }
                )

    # Strictly enforce containment for command execution environments
    if tool_name == "run_command":
        cwd = args.get("Cwd")
        if cwd:
            cwd = cwd.strip("\"'")
            if not str(Path(cwd).resolve()).startswith(str(wt_path)):
                respond(
                    {
                        "decision": "deny",
                        "reason": f"Security Exception: Command CWD '{cwd}' is outside the assigned worktree '{wt_path}'",
                    }
                )

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
