"""Invoke Claude Opus 4.6 (Thinking) to ratify the Founder Directive:

1. Tauri 2.0 (Rust Core) Mac Desktop Application (overriding Electron).
2. Cloud-First Mobile Remote Control Architecture (Standalone phone operation, LiveKit Eva meetings, cloud dispatch).
3. Cloud Provisioning QR Pairing Protocol.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")


def run_amendment():
    print("\n🏛️ [AMENDMENT DEBATE] Invoking Claude Opus 4.6 (Thinking)...")

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["RATIFIED_AMENDMENT"]},
            "architectural_synthesis": {
                "type": "string",
                "description": "Comprehensive synthesis of the Cloud-First Remote Control architecture and Tauri Rust desktop node"
            },
            "tauri_rust_mac_spec": {
                "type": "object",
                "properties": {
                    "architecture": {"type": "string"},
                    "rust_core_responsibilities": {"type": "string"},
                    "react_frontend_integration": {"type": "string"},
                    "screens": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["architecture", "rust_core_responsibilities", "react_frontend_integration", "screens"]
            },
            "mobile_cloud_remote_control_spec": {
                "type": "object",
                "properties": {
                    "standalone_capabilities": {"type": "string"},
                    "livekit_eva_meetings": {"type": "string"},
                    "remote_task_dispatch_flow": {"type": "string"},
                    "screens": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["standalone_capabilities", "livekit_eva_meetings", "remote_task_dispatch_flow", "screens"]
            },
            "cloud_provisioning_qr_protocol": {
                "type": "string",
                "description": "Specification of the dynamic QR code for cloud provisioning and cluster pairing"
            },
            "section_14_2_amended_markdown": {
                "type": "string",
                "description": "Complete replacement markdown for Section 14.2 in docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md"
            }
        },
        "required": [
            "verdict",
            "architectural_synthesis",
            "tauri_rust_mac_spec",
            "mobile_cloud_remote_control_spec",
            "cloud_provisioning_qr_protocol",
            "section_14_2_amended_markdown"
        ],
        "additionalProperties": False
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = """You are Claude Opus 4.6 (Thinking), Supreme Lead Architect for AlphaBrain.
You hold exclusive authoring authority over `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.

CRITICAL INSTRUCTION:
You are in PURE ARCHITECTURAL PLANNING MODE.
DO NOT invoke any tools, shell commands, or bash scripts.
DO NOT spawn or consult any subagents.
Output strictly the structured JSON object matching the JSON schema.

FOUNDER ARCHITECTURAL DIRECTIVE & CORRECTION:
The Founder has reviewed your prior review and issued two binding structural directives:

1. TAURI (RUST CORE) RATIFICATION (Overturning Electron):
   The Founder explicitly favors the Rust-based architecture proposed by Gemini in Round 1:
   - Mac Desktop App must be built using Tauri 2.0 (Rust core) + React 19 / Vite + Tailwind CSS.
   - Compiles to a lightweight native binary (~15MB, ~30-50MB RAM vs Electron's 500MB+ bloat).
   - Rust core provides native macOS NSStatusItem menu bar integration, native Keychain storage via `security-framework`, and native process management for spawning local `alpha_worker.daemon` and `agy` CLI subagents.
   - Frontend shares 100% of React 19 components and Locomotive design tokens with the mobile app.

2. CLOUD-FIRST REMOTE CONTROL PARADIGM (No Local Tethering):
   - The Mobile Companion is NOT a tethered slave to the Mac. It is a standalone executive Remote Control connecting directly to the Central Production Backend (`https://api.alphabrain.live` or user host).
   - Remote Execution Flow:
     * Founder on 5G taps "Approve & Execute Task TSK-042" on phone.
     * Request hits Central Production Backend.
     * Central Production Backend assigns execution lease to the registered Mac App Node (running at founder's desk).
     * Mac App executes task in isolated Git worktree via local daemon, runs tests, and streams terminal logs back to Central Backend.
     * Central Backend broadcasts live logs directly to Founder's phone in real time.
     * Founder reviews diff and taps "Merge" from anywhere in the world!
   - Full Mobile Standalone Capabilities:
     * When Founder has no Mac nearby (traveling/on mobile), they have FULL functionality:
       - Join LiveKit voice/video meetings with Eva directly from phone (`POST /api/meet/token`).
       - Triage, approve, reject tasks.
       - View live telemetry, quotas, and deployments.
   - Re-defined QR Code:
     * The QR code displayed on the Mac App (or cloud web console) is an Account Provisioning & Cluster Pairing QR code.
     * Scanning it securely passes the cloud auth session and registers the Mac execution node to the Founder's account without typing 64-character tokens.

YOUR TASKS:
1. Ratify Tauri 2.0 (Rust core) for the Mac Desktop App.
2. Formalize the Cloud-First Remote Control & Dispatch Architecture.
3. Formalize the direct Mobile LiveKit Eva meeting integration.
4. Specify the 4 Mac Desktop screens (Tauri) and 15 Mobile screens (Capacitor).
5. Author the complete, amended Section 14.2 markdown for `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.
"""

    cmd = [
        "agy",
        "--model",
        "claude-opus-4-6-thinking",
        "--dangerously-skip-permissions",
        "--mode",
        "plan",
        "--output-format",
        "json",
        "--input-format",
        "text",
        "--json-schema",
        schema_file,
        "--print-timeout",
        "480s",
    ]

    try:
        res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=WORKSPACE_ROOT, timeout=420)
        if res.returncode != 0:
            print(f"Opus Amendment Error: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        raw_stdout = res.stdout.strip()
        data = json.loads(raw_stdout)

        if "structured_output" in data:
            ratification = data["structured_output"]
        elif "verdict" in data:
            ratification = data
        elif "response" in data and isinstance(data["response"], dict):
            ratification = data["response"]
        elif "response" in data and isinstance(data["response"], str):
            try:
                ratification = json.loads(data["response"])
            except Exception:
                ratification = data
        else:
            ratification = data

        output_path = WORKSPACE_ROOT / "testscript" / "opus_amended_remote_control.json"
        with open(output_path, "w") as out_f:
            json.dump(ratification, out_f, indent=2)
        print(f"✅ [AMENDMENT RATIFIED] Saved to {output_path}")

        # Update SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md
        section_md = ratification.get("section_14_2_amended_markdown", "")
        if section_md:
            directive_file = WORKSPACE_ROOT / "docs" / "architecture" / "SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md"
            content = directive_file.read_text()
            # Replace previous 14.2 review with the amended version
            marker = "# Section 14.2 — Senior Architectural Review & Ratification"
            if marker in content:
                idx = content.find(marker)
                new_content = content[:idx].rstrip() + "\n\n---\n\n" + section_md.strip() + "\n"
            else:
                new_content = content.rstrip() + "\n\n---\n\n" + section_md.strip() + "\n"
            directive_file.write_text(new_content)
            print("📜 [DIRECTIVE UPDATED] Section 14.2 amended in SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md")

    finally:
        Path(schema_file).unlink(missing_ok=True)


if __name__ == "__main__":
    run_amendment()
