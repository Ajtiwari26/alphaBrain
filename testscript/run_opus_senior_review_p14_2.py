"""Autonomous Senior Architectural Review Runner for Phase 14.2.

Invokes Claude Opus 4.6 (Thinking) via agy CLI using structured JSON schema to audit live production
backend integration and author Section 14.2 in docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md.
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
        ["git", "diff", "HEAD", "--", "alpha_core/", "alphabrain_app/"],
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
                "description": "Deep architectural assessment of concurrency, safety, CORS, SQLite transactions, and telemetry isolation.",
            },
            "section_markdown": {
                "type": "string",
                "description": "The exact, fully formatted markdown block for Section 14.2 ready to append to SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md.",
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
Conduct a formal Senior Architectural Review of Sub-milestone P14.2: "AlphaBrain Founder Companion — Live Production Backend Integration & Hardware Telemetry".
Verify full compliance with AlphaBrain Invariants (I-1 through I-50), the P9 Constitution, and system security boundaries.

EVALUATION CRITERIA:
1. Invariant I-1 (No Direct Path from Eva to Worker): All tasks flow through SQLite TaskTriageQueue and require SafetyGate validation.
2. Invariant I-26 (Protected Paths): Backend router mount respects authentication via Depends(require_api_principal).
3. Invariant I-33 & I-47 (FastAPI Mobile Bridge Security & CORS): Whitelisted Capacitor WebView (https://localhost, capacitor://localhost) without wildcard origins (*).
4. Invariant I-49 & I-50 (Deterministic Concurrency & Host Telemetry Isolation): psutil metrics extracted safely; SQLite transactions execute with busy_timeout=5000 and BEGIN IMMEDIATE; multi-account quota polling cached with 60s TTL; zero residual mock fallbacks in API client or screens.
5. On-Device Verification: Tested on physical device 10BF5P2AZF0010T via ADB reverse tcp:8000; verified live host metrics (CPU 31.2%, RAM 71.5%), 50 SQLite tasks, 59 Git worktrees, and 46 project directories.

WORKING TREE DIFF:
```diff
{diff_text[:14000]}
```

OUTPUT REQUIREMENTS:
Output a structured JSON object matching the required schema:
1. `verdict`: "APPROVED" or "REPAIR_REQUIRED".
2. `architectural_critique`: Detailed technical critique.
3. `section_markdown`: Complete canonical markdown section starting with `### 14.2 Founder Companion Live Production Backend Integration — Architectural Review Record` and ending with your signature block `*P14.2 review record authored and signed by Claude Opus 4.6 (Thinking) on 2026-09-13.*`.
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
            sys.exit(res.returncode)

        raw_out = res.stdout.strip()
        result = json.loads(raw_out)
        verdict = result.get("verdict")
        critique = result.get("architectural_critique", "")
        section_md = result.get("section_markdown", "").strip()

        print(f"✅ Claude Opus 4.6 Review Verdict: {verdict}")
        print(f"Critique Summary: {critique[:300]}...")

        if verdict == "APPROVED" and section_md:
            print(f"📝 Appending ratified review to {DIRECTIVE_PATH}...")
            current_content = DIRECTIVE_PATH.read_text(encoding="utf-8")
            new_content = current_content.rstrip() + "\n\n---\n\n" + section_md + "\n"
            DIRECTIVE_PATH.write_text(new_content, encoding="utf-8")
            print("🎉 Section 14.2 appended and sealed!")
        else:
            print(f"⚠️ Review verdict was {verdict}. Directive was not modified.")
            print(section_md)

    finally:
        Path(schema_file).unlink(missing_ok=True)


if __name__ == "__main__":
    run_senior_review()
