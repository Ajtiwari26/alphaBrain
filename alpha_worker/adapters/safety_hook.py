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
    args = tool_call.get("args", {})
    
    worktree_path = os.environ.get("ALPHA_WORKTREE_PATH")
    if not worktree_path:
        print(json.dumps({"decision": "deny", "reason": "Missing ALPHA_WORKTREE_PATH environment variable."}))
        sys.exit(0)
        
    wt_path = Path(worktree_path).resolve()

    # Extract any argument that looks like an absolute path and verify it's within the worktree
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("/"):
            try:
                target_path = Path(v).resolve()
                if not str(target_path).startswith(str(wt_path)):
                    print(json.dumps({
                        "decision": "deny", 
                        "reason": f"Security Exception: Path '{v}' is outside the assigned worktree '{wt_path}'"
                    }))
                    sys.exit(0)
            except Exception:
                pass
                
    # If no path checks failed, we programmatically allow the execution
    print(json.dumps({"decision": "allow", "reason": "Worktree containment verified by programmatic hook."}))

if __name__ == "__main__":
    main()
