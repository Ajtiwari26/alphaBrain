#!/usr/bin/env python3
"""
Two-Round Senior Engineering Review for Etta Full Google AI Pro Federation & agy Parity.
Round 1: Gemini 3.1 Pro High (Senior Systems & Transport Auditor)
Round 2: Claude Opus 4.6 Thinking (Supreme Lead Architect & Arbiter)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")
ETTA_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/etta")
PLAN_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "TIER0_ASTRA_ETTA_GOOGLE_AI_FEDERATION_PLAN.md"


def load_plan_text() -> str:
    if not PLAN_PATH.exists():
        raise FileNotFoundError(f"Plan file not found: {PLAN_PATH}")
    return PLAN_PATH.read_text(encoding="utf-8")


def run_round_1_gemini(plan_text: str) -> dict:
    print("\n" + "=" * 80)
    print("🚀 [ROUND 1] Invoking Gemini 3.1 Pro High (Senior Systems & Transport Auditor)...")
    print("=" * 80 + "\n")

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["AMEND", "APPROVE"]},
            "executive_audit_summary": {"type": "string"},
            "transport_streaming_critique": {
                "type": "object",
                "properties": {
                    "http2_sse_concurrency_risks": {"type": "string"},
                    "thinking_trace_demuxing": {"type": "string"},
                    "backpressure_and_flow_control": {"type": "string"},
                },
                "required": ["http2_sse_concurrency_risks", "thinking_trace_demuxing", "backpressure_and_flow_control"],
            },
            "credentials_federation_critique": {
                "type": "object",
                "properties": {
                    "keychain_security_risks": {"type": "string"},
                    "oc_eds_rotation_soundness": {"type": "string"},
                    "token_refresh_race_conditions": {"type": "string"},
                },
                "required": ["keychain_security_risks", "oc_eds_rotation_soundness", "token_refresh_race_conditions"],
            },
            "tool_primitives_parity_critique": {
                "type": "object",
                "properties": {
                    "replace_file_content_edge_cases": {"type": "string"},
                    "pty_terminal_and_mcp_isolation": {"type": "string"},
                    "sqlite_rollback_concurrency": {"type": "string"},
                },
                "required": ["replace_file_content_edge_cases", "pty_terminal_and_mcp_isolation", "sqlite_rollback_concurrency"],
            },
            "recommended_amendments": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "verdict",
            "executive_audit_summary",
            "transport_streaming_critique",
            "credentials_federation_critique",
            "tool_primitives_parity_critique",
            "recommended_amendments",
        ],
        "additionalProperties": False,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = f"""You are Gemini 3.1 Pro High, Senior Systems & Transport Auditor for AlphaBrain.

TASK OVERVIEW:
Execute an in-depth structural, concurrency, and protocol audit on the proposed Etta Google AI Pro Federation & 100% agy Parity Architecture Plan.

PLAN SPECIFICATION TO AUDIT:
{plan_text}

AUDIT MANDATE:
1. Transport & Streaming: Audit the async HTTP/2 SSE streaming client calling `streamGenerateContent`. Verify demuxing of thinking tokens into the HUD drawer vs code deltas. Analyze backpressure when tokens arrive at ~170 TPS.
2. Credential Federation: Audit macOS Keychain password retrieval (`security`), multi-account OAuth2 token refreshing, and live OC-EDS rotation across the 8 Google AI Pro accounts. Identify any token refresh race conditions.
3. 55+ Tool Primitives: Audit exact multi-chunk line replacement (`replace_file_content`), PTY process supervision, and MCP JSON-RPC stdio client isolation.
4. SQLite Checkpointing & Rollback: Verify that taking a CAS checkpoint before every mutation in <4.5ms preserves 100% workspace safety.

Emit your structured JSON audit report strictly matching the JSON schema.
"""

    cmd = [
        "agy",
        "--model",
        "gemini-3.1-pro-high",
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
        "300s",
    ]

    try:
        res = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            timeout=360,
        )
        if res.returncode != 0:
            print(f"Gemini Round 1 Error: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        data = json.loads(res.stdout)
        proposal = data.get("structured_output") or data
        out_path = ETTA_ROOT / "docs" / "architecture" / "ROUND1_GEMINI_AUDIT_FULL_PARITY.json"
        with open(out_path, "w", encoding="utf-8") as out_f:
            json.dump(proposal, out_f, indent=2)

        print(f"✅ [ROUND 1 COMPLETE] Gemini Pro audit saved to {out_path}")
        return proposal
    finally:
        Path(schema_file).unlink(missing_ok=True)


def run_round_2_opus(r1_audit: dict, plan_text: str) -> dict:
    print("\n" + "=" * 80)
    print("👑 [ROUND 2] Invoking Claude Opus 4.6 Thinking (Supreme Lead Architect & Arbiter)...")
    print("=" * 80 + "\n")

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["FINAL_APPROVAL"]},
            "senior_synthesis": {"type": "string"},
            "subsystem_invariants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Numbered system invariants (e.g. INV-ETTA-01 to INV-ETTA-10)",
            },
            "binding_work_packets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "packet_id": {"type": "string"},
                        "title": {"type": "string"},
                        "scope": {"type": "string"},
                        "acceptance_criteria": {"type": "string"},
                    },
                    "required": ["packet_id", "title", "scope", "acceptance_criteria"],
                },
            },
            "canonical_markdown": {
                "type": "string",
                "description": "Formal Markdown directive ready to be ratified into docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md",
            },
        },
        "required": [
            "verdict",
            "senior_synthesis",
            "subsystem_invariants",
            "binding_work_packets",
            "canonical_markdown",
        ],
        "additionalProperties": False,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = f"""You are Claude Opus 4.6 Thinking, Supreme Lead Architect for AlphaBrain and DeployMate Etta.
You hold exclusive authoring authority over `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.

TASK OVERVIEW:
Review the proposed Etta Google AI Pro Federation & 100% agy Parity Architecture Plan along with Gemini 3.1 Pro High's Round 1 Structural Audit. Synthesize trade-offs, ratify core invariants, and author binding engineering directives.

PROPOSED FULL PARITY PLAN:
{plan_text}

ROUND 1 STRUCTURAL AUDIT (GEMINI 3.1 PRO HIGH):
{json.dumps(r1_audit, indent=2)}

YOUR MANDATE:
1. Synthesize Gemini's critique regarding HTTP/2 SSE streaming, token demuxing, and backpressure.
2. Formalize the 8-Account Google AI Pro Federation and live OC-EDS rotation invariants.
3. Ratify the complete 55+ Tool Primitives Parity and the mandatory <4.5ms SQLite CAS rollback invariant.
4. Define binding implementation Work Packets (WP-01 through WP-05) for the autonomous worker cycle.
5. Provide complete, comprehensive Markdown ready to seal into `SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.
"""

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
        "400s",
    ]

    try:
        res = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            timeout=480,
        )
        if res.returncode != 0:
            print(f"Claude Opus Round 2 Error: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        data = json.loads(res.stdout)
        synthesis = data.get("structured_output") or data
        out_json = ETTA_ROOT / "docs" / "architecture" / "ROUND2_OPUS_SYNTHESIS_FULL_PARITY.json"
        out_md = ETTA_ROOT / "docs" / "architecture" / "SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN_FULL_PARITY.md"

        with open(out_json, "w", encoding="utf-8") as out_f:
            json.dump(synthesis, out_f, indent=2)

        with open(out_md, "w", encoding="utf-8") as out_f:
            out_f.write(synthesis.get("canonical_markdown", ""))

        print(f"✅ [ROUND 2 COMPLETE] Opus synthesis saved to {out_json} and {out_md}")
        return synthesis
    finally:
        Path(schema_file).unlink(missing_ok=True)


def main():
    plan_text = load_plan_text()
    r1 = run_round_1_gemini(plan_text)
    r2 = run_round_2_opus(r1, plan_text)
    print("\n" + "=" * 80)
    print("🏆 TWO-ROUND SENIOR ENGINEERING REVIEW SUCCESSFULLY COMPLETED")
    print(f"Round 1 Verdict: {r1.get('verdict')}")
    print(f"Round 2 Verdict: {r2.get('verdict')}")
    print("=" * 80)


if __name__ == "__main__":
    main()
