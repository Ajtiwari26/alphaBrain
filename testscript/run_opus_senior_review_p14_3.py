"""Autonomous Senior Architectural Review Runner for Phase 14.3 (Delivery Board & Client Governance).

Invokes Claude Opus 4.6 (Thinking) via agy CLI using structured JSON schema to audit:
1. Amazon-Style Delivery Board & Milestone Status Tracker.
2. Executive Architecture Reading Room with Read-Only Opus Directive Invariant.
3. Client & Delegate Access Control (CLT-XXXX / ALPHA-XXXX) and Admin Delegation.
4. Client Feedback Ingestion, Eva AI Diagnostic Synthesis, and Strict Admin Handover to TaskTriageQueue.

ONLY Claude Opus 4.6 (Thinking) appends Section 14.3 to docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")
DIRECTIVE_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md"


def get_git_diff() -> str:
    res = subprocess.run(
        [
            "git",
            "diff",
            "307b3d7..HEAD",
            "--",
            "alpha_core/mobile_bridge/",
            "alphabrain_app/src/screens/",
            "alphabrain_app/src/types.ts",
            "alphabrain_app/src/api/client.ts",
            "testscript/test_delivery_board_and_delegates.py",
        ],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
    )
    return res.stdout or "No changes detected in working tree."


def run_senior_review():
    print("📡 Collecting review context...")
    diff_text = get_git_diff()

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["APPROVED", "REPAIR_REQUIRED"],
            },
            "architectural_critique": {
                "type": "string",
                "description": "Deep architectural assessment of delivery milestone state machine, client query isolation, Eva diagnostic synthesis, and strict admin approval invariant before triage queue admission.",
            },
            "section_markdown": {
                "type": "string",
                "description": "The exact, fully formatted markdown block for Section 14.3 ready to append to SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md.",
            },
        },
        "required": ["verdict", "architectural_critique", "section_markdown"],
        "additionalProperties": False,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = f"""You are Claude Opus 4.6 (Thinking), Supreme Lead Architect for AlphaBrain.
You hold exclusive write and modification authority over `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.

MISSION:
Conduct a formal Senior Architectural Review of Sub-milestone P14.3: "Amazon-Style Delivery Board, Executive Architecture Reading Room, Client Delegate Access & Admin Handover Governance".
Verify full compliance with AlphaBrain Invariants (I-1 through I-60), the Founder's strict governance directive, and system security boundaries.

EVALUATION CRITERIA:
1. Invariant I-1 & Founder Directive (Strict Admin Permission Invariant): Client queries and problem tickets must NEVER trigger automated code modifications, branch creation, or worktree dispatch without explicit Founder or Delegated Admin sign-off.
2. Invariant I-26 & I-47 (Cryptographic Task Admission): When Admin triggers "Handover to Pipeline", the task is formally admitted through EvaTaskProposer with a canonical cryptographic envelope, TaskProvenance, and SafetyGate evaluation, enqueuing into SQLite TaskTriageQueue.
3. Reading Room Authority Invariant: docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md is strictly read-only to all models, subagents, and client delegates; only Claude Opus authors and updates it.
4. Milestone Progression & In-Flight Worktree Radar: The 7-stage delivery board (Inception -> Safety Gate -> Consensus Planning -> Worktree Worker -> 2-Round Review -> Fast-Forward Merge -> Live Telemetry) is dynamically mapped to real tasks in SQLite.
5. On-Device & Web Verification: All 3 tabs verified live via Chrome DevTools MCP with zero console errors and 100% pass on testscript/test_delivery_board_and_delegates.py.

WORKING TREE DIFF:
```diff
{diff_text[:14000]}
```

OUTPUT REQUIREMENTS:
Output a structured JSON object matching the required schema:
1. `verdict`: "APPROVED" or "REPAIR_REQUIRED".
2. `architectural_critique`: Detailed technical critique.
3. `section_markdown`: Complete canonical markdown section starting with `### 14.3 Amazon-Style Delivery Board & Client Delegate Governance — Architectural Ratification Record` and ending with your signature block `*P14.3 review record authored and signed by Claude Opus 4.6 (Thinking) on 2026-09-16.*`.
"""

    print("🧠 Invoking Claude Opus 4.6 (Thinking) via agy CLI with structured schema...")
    cmd = [
        "agy",
        "--model",
        "claude-opus-4-6-thinking",
        "--sandbox",
        "--mode",
        "plan",
        "--output-format",
        "json",
        "--input-format",
        "text",
        "--json-schema",
        schema_file,
        "--print-timeout",
        "600s",
    ]

    try:
        res = subprocess.run(
            cmd,
            input=prompt,
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            timeout=660,
        )
        if res.returncode != 0:
            print(f"❌ Opus invocation failed (code {res.returncode}):\n{res.stderr}", file=sys.stderr)
            sys.exit(1)

        raw_output = res.stdout.strip()
        data = json.loads(raw_output)

        if "structured_output" in data and isinstance(data["structured_output"], dict):
            payload = data["structured_output"]
        elif "response" in data and isinstance(data["response"], dict):
            payload = data["response"]
        elif "response" in data and isinstance(data["response"], str):
            try:
                payload = json.loads(data["response"])
            except Exception:
                payload = data
        else:
            payload = data

        verdict = payload.get("verdict")
        critique = payload.get("architectural_critique")
        section_md = payload.get("section_markdown")

        print("\n=======================================================")
        print(f"🏛️ CLAUDE OPUS 4.6 (THINKING) VERDICT: {verdict}")
        print("=======================================================\n")
        print(f"Architectural Critique:\n{critique}\n")

        if verdict == "APPROVED" and section_md:
            print(f"📝 Ratifying Section 14.3 into {DIRECTIVE_PATH.name}...")
            with open(DIRECTIVE_PATH, encoding="utf-8") as f:
                existing_content = f.read().rstrip()

            updated_content = existing_content + "\n\n" + section_md.strip() + "\n"
            with open(DIRECTIVE_PATH, "w", encoding="utf-8") as f:
                f.write(updated_content)

            print("✅ Successfully ratified Section 14.3 by Claude Opus 4.6 (Thinking)!")
        else:
            print("❌ Review was not approved or missing section markdown.", file=sys.stderr)
            sys.exit(2)

    except Exception as e:
        print(f"❌ Error during Opus review execution: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_senior_review()
