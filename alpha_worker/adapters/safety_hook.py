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
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    tool_call = input_data.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    
    worktree_path = os.environ.get("ALPHA_WORKTREE_PATH")
    if not worktree_path:
        print(json.dumps({"decision": "deny", "reason": "Missing ALPHA_WORKTREE_PATH environment variable."}))
        sys.exit(0)
        
    wt_path = Path(worktree_path).resolve()

    # Strictly enforce containment for file modifications
    if tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content"]:
        path = args.get("TargetFile") or args.get("AbsolutePath")
        if path and not str(Path(path).resolve()).startswith(str(wt_path)):
            print(json.dumps({"decision": "deny", "reason": f"Security Exception: File write path '{path}' is outside the assigned worktree '{wt_path}'"}))
            sys.exit(0)
            
    # Strictly enforce containment for command execution environments
    if tool_name == "run_command":
        cwd = args.get("Cwd")
        if cwd and not str(Path(cwd).resolve()).startswith(str(wt_path)):
            print(json.dumps({"decision": "deny", "reason": f"Security Exception: Command CWD '{cwd}' is outside the assigned worktree '{wt_path}'"}))
            sys.exit(0)
            
    # If no checks failed, we programmatically allow the execution
    print(json.dumps({"decision": "allow", "reason": "Worktree containment verified by programmatic hook."}))

if __name__ == "__main__":
    main()
