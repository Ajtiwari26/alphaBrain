"""Dry-run admission proof for a future founder-approved AlphaBrain self-task."""

from __future__ import annotations

import argparse
from pathlib import Path

from alpha_core.self_development import SelfImprovementRequest, admit_self_improvement
from alpha_protocol import RiskClass


def main(args_list: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Validate a founder-approved self-task")
    parser.add_argument("--approve-as", default="", help="Founder identity recorded for admission")
    parser.add_argument("--source-repo", default=".", help="AlphaBrain repository to validate")
    parser.add_argument(
        "--allowed-path",
        action="append",
        default=[],
        help="Relative path an eventual self-task may modify; repeatable",
    )
    args = parser.parse_args(args_list)

    if not args.live:
        print("Dry run only. Use --live --approve-as with explicit --allowed-path values.")
        return 0

    admission = admit_self_improvement(
        SelfImprovementRequest(
            source_repo=Path(args.source_repo),
            allowed_paths=tuple(args.allowed_path),
            founder_identity=args.approve_as,
            requires_approval=True,
            risk_class=RiskClass.LOW,
        )
    )
    if not admission.admitted:
        print(f"Self-improvement admission rejected: {admission.reason}")
        return 1

    print(f"Self-improvement admission accepted at immutable base {admission.base_commit}")
    print("No task, worktree, commit, or source mutation was created by this admission proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
