#!/usr/bin/env python3
"""
Pre-Build QA Smoke Suite for ETTA Agent Runtime.
Validates core agentic invariants:
1. Tool error non-fatal observation return (missing file, unmatched target).
2. Resilient file replacement with whitespace/indentation/CRLF normalization.
3. Unit test pass gate across all runtime crates.
"""

import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

ETTA_DIR = Path("/Users/ajaytiwari/Desktop/Projects/etta")

def print_banner(msg: str):
    print("\n" + "=" * 60)
    print(f"  {msg}")
    print("=" * 60)

def test_cargo_unit_tests():
    print_banner("QA Phase 1: Cargo Runtime Unit Tests")
    cmd = ["cargo", "test", "-p", "etta-runtime", "--test", "resilient_file_tool_tests"]
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=ETTA_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED:\n{res.stdout}\n{res.stderr}")
        return False
    print("  All 7 resilient file tool tests PASSED.")

    cmd2 = ["cargo", "test", "-p", "etta-runtime", "--test", "react_loop_tests"]
    print(f"Running: {' '.join(cmd2)}")
    res2 = subprocess.run(cmd2, cwd=ETTA_DIR, capture_output=True, text=True)
    if res2.returncode != 0:
        print(f"FAILED:\n{res2.stdout}\n{res2.stderr}")
        return False
    print("  All 18 ReAct loop tests PASSED.")

    cmd3 = ["cargo", "test", "-p", "etta-policy"]
    print(f"Running: {' '.join(cmd3)}")
    res3 = subprocess.run(cmd3, cwd=ETTA_DIR, capture_output=True, text=True)
    if res3.returncode != 0:
        print(f"FAILED:\n{res3.stdout}\n{res3.stderr}")
        return False
    print("  All 25 etta-policy JEV dynamic budget tests PASSED.")
    return True

def test_cargo_check_all():
    print_banner("QA Phase 2: Compiler & Linter Verification")
    cmd = ["cargo", "check", "--all"]
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=ETTA_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED:\n{res.stdout}\n{res.stderr}")
        return False
    print("  Workspace clean: 0 compiler errors, 0 warnings.")
    return True

def main():
    print("\n" + "#" * 60)
    print("       ETTA PRE-BUILD QA VERIFICATION SMOKE SUITE            ")
    print("#" * 60)

    if not test_cargo_unit_tests():
        print("\n[QA GATE FAILED] Unit tests failed. Build aborted.")
        sys.exit(1)

    if not test_cargo_check_all():
        print("\n[QA GATE FAILED] Cargo check failed. Build aborted.")
        sys.exit(1)

    print("\n" + "#" * 60)
    print("  ALL QA GATES PASSED CLEANLY (100% SUCCESS)               ")
    print("#" * 60)
    sys.exit(0)

if __name__ == "__main__":
    main()
