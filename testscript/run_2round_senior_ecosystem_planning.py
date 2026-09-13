"""Two-Round Senior Planning & Architectural Framing: AlphaBrain Mac App, Mobile QR Sync, and Production Backend.

Round 1: Gemini 3.1 Pro High (Lead Systems & Network Architect)
Round 2: Claude Opus 4.6 Thinking (Supreme Lead Architect & Arbiter)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")


def run_round_1_gemini(context: dict) -> dict:
    print("\n" + "="*80)
    print("🚀 [ROUND 1] Invoking Gemini 3.1 Pro High (Lead Systems & Network Architect)...")
    print("="*80 + "\n")

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PROPOSAL_READY"]},
            "ecosystem_topology": {"type": "string", "description": "Three-tier architecture topology (Mac App, Mobile App, Cloud Backend)"},
            "qr_pairing_protocol": {
                "type": "object",
                "properties": {
                    "cryptographic_primitives": {"type": "string"},
                    "qr_payload_schema": {"type": "string"},
                    "rotation_and_expiry": {"type": "string"},
                    "mutual_handshake_flow": {"type": "string"}
                },
                "required": ["cryptographic_primitives", "qr_payload_schema", "rotation_and_expiry", "mutual_handshake_flow"]
            },
            "mac_application_spec": {
                "type": "object",
                "properties": {
                    "tech_stack": {"type": "string"},
                    "screen_m01_node_setup": {"type": "string"},
                    "screen_m02_pairing_station": {"type": "string"},
                    "screen_m03_desktop_command_node": {"type": "string"},
                    "screen_m04_security_enclave": {"type": "string"}
                },
                "required": ["tech_stack", "screen_m01_node_setup", "screen_m02_pairing_station", "screen_m03_desktop_command_node", "screen_m04_security_enclave"]
            },
            "mobile_companion_spec": {
                "type": "object",
                "properties": {
                    "screen_01_splash": {"type": "string"},
                    "screen_02a_enrollment": {"type": "string"},
                    "screen_02b_access_gate": {"type": "string"},
                    "screen_03_qr_scanner_bridge": {"type": "string"},
                    "screen_04_command_center": {"type": "string"}
                },
                "required": ["screen_01_splash", "screen_02a_enrollment", "screen_02b_access_gate", "screen_03_qr_scanner_bridge", "screen_04_command_center"]
            },
            "production_backend_integration": {
                "type": "object",
                "properties": {
                    "api_endpoints": {"type": "array", "items": {"type": "string"}},
                    "websocket_channels": {"type": "array", "items": {"type": "string"}},
                    "security_and_auth": {"type": "string"}
                },
                "required": ["api_endpoints", "websocket_channels", "security_and_auth"]
            }
        },
        "required": ["verdict", "ecosystem_topology", "qr_pairing_protocol", "mac_application_spec", "mobile_companion_spec", "production_backend_integration"],
        "additionalProperties": False
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = f"""You are Gemini 3.1 Pro High, Lead Systems & Network Architect for AlphaBrain.

TASK OVERVIEW:
Formulate the comprehensive Round 1 Architectural Blueprint for the AlphaBrain Mac Application, Mobile Companion App QR Sync Flow, and Production Backend Integration.

USER DIRECTIVE:
"like a alphabrain mac application. and mobile app proper sysnc setup like setup of mac app then in that there will be a setup shows qr to connect the app to this mac application to the mobile one and then user setup the mobile app and scan the qr from phone and then both devices get connect , we need a proper plan for the workflow how the mac app and mobile app should sync and connect and based on this plan we need to redesign the then existing app design and new screens if required and also we need to design the mac application screens too , give seniors the context of alphbrian working and app working mac applicaiton working and the curent screen md file then give them task to prepare flow how these things work and connect mac application and mobile application to production backend and what else required"

EXISTING MOBILE SPECIFICATIONS:
{context['mobile_screens_summary']}

USER VISUAL ASSETS:
1. Splash Screen (media_1789280907273.png): Minimalist white canvas, 3D Alpha mesh symbol, bold AlphaBrain, POWERED BY DeployMate logo, 2s auto-handoff.
2. Founder Access Gate (media_1789280951800.png): 02 // ACCESS GATE, STAGE 2/3, Founder Access, Touch ID box, 4 square PIN boxes, Keypad with [AUTO] in red, [0], [⌫], and bottom Instant Founder Biometric Unlock.

DELIVERABLES:
1. Three-tier ecosystem topology (Cloud Backend, Mac Desktop Node, Mobile Companion).
2. Dynamic QR Pairing Protocol (ECDH P-256 key exchange, Ed25519 signing, 120s rotation nonce, mutual confirmation).
3. Mac Application Architecture & 4 Screens (Setup & Cloud Link, Pairing QR Station, Command Node, Security Enclave).
4. Redesigned Mobile Companion Flow (Splash -> Enrollment -> QR Scanner -> Confirmation -> Access Gate -> Dashboard).
5. Production Backend Integration (FastAPI endpoints under /api/v1/pairing/*, WebSocket events, token verification).
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
        res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=WORKSPACE_ROOT, timeout=360)
        if res.returncode != 0:
            print(f"Gemini Round 1 Error: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)
        data = json.loads(res.stdout)
        proposal = data.get("structured_output") or data
        with open(WORKSPACE_ROOT / "testscript" / "round1_gemini_ecosystem_proposal.json", "w") as out_f:
            json.dump(proposal, out_f, indent=2)
        print("✅ [ROUND 1 COMPLETE] Gemini Pro proposal generated successfully.")
        return proposal
    finally:
        Path(schema_file).unlink(missing_ok=True)


def run_round_2_opus(context: dict, r1_proposal: dict) -> dict:
    print("\n" + "="*80)
    print("🏛️ [ROUND 2] Invoking Claude Opus 4.6 (Thinking) (Supreme Lead Architect)...")
    print("="*80 + "\n")

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["APPROVED_RATIFIED", "REPAIRS_REQUIRED"]},
            "senior_critique_and_gap_analysis": {
                "type": "string",
                "description": "Critique of Round 1 proposal, threat modeling, attack surfaces, and missing edge cases"
            },
            "formal_state_machine_invariants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Binding invariants for the Mac app, Mobile app, and Backend pairing states"
            },
            "security_and_cryptographic_ratification": {
                "type": "string",
                "description": "Ratified crypto spec (P-256 ECDH, Ed25519 signatures, replay window, revocation, biometric enclave)"
            },
            "mac_desktop_canonical_screens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "screen_id": {"type": "string"},
                        "name": {"type": "string"},
                        "layout": {"type": "string"},
                        "interactions": {"type": "string"}
                    },
                    "required": ["screen_id", "name", "layout", "interactions"]
                }
            },
            "mobile_companion_canonical_screens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "screen_id": {"type": "string"},
                        "name": {"type": "string"},
                        "layout": {"type": "string"},
                        "interactions": {"type": "string"}
                    },
                    "required": ["screen_id", "name", "layout", "interactions"]
                }
            },
            "section_14_2_canonical_markdown": {
                "type": "string",
                "description": "Complete, formal Section 14.2 markdown ready to seal into docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md"
            }
        },
        "required": [
            "verdict",
            "senior_critique_and_gap_analysis",
            "formal_state_machine_invariants",
            "security_and_cryptographic_ratification",
            "mac_desktop_canonical_screens",
            "mobile_companion_canonical_screens",
            "section_14_2_canonical_markdown"
        ],
        "additionalProperties": False
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = f"""You are Claude Opus 4.6 (Thinking), Supreme Lead Architect for AlphaBrain.
You hold exclusive authoring authority over `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.

CRITICAL INSTRUCTION:
You are operating in PURE ARCHITECTURAL PLANNING MODE.
DO NOT invoke any tools, shell commands, or bash scripts.
DO NOT spawn or consult any subagents.
All required codebase context, screen catalogs, and round 1 proposals are fully provided below.
Your single mandate is to directly return the structured JSON object adhering strictly to the JSON schema.

YOUR ROLE IN THIS 2-ROUND DEBATE:
Critique, refine, strengthen, and formally ratify the Round 1 System Proposal formulated by Gemini 3.1 Pro High for the AlphaBrain Mac Desktop Application, Mobile Companion QR Synchronization Flow, and Production Backend Integration.

ROUND 1 BLUEPRINT FROM GEMINI PRO HIGH:
{json.dumps(r1_proposal, indent=2)}

USER DIRECTIVE & VISUAL BENCHMARKS:
1. The user requires an integrated AlphaBrain Mac Application and Mobile App proper sync setup:
   - Mac App displays a dynamic QR Code during pairing setup.
   - Mobile app opens camera, scans QR from Mac screen.
   - Mutual connection established instantly, syncing node state, telemetry, and live agent worktrees.
   - Full screen designs for both Mac Application and Mobile Companion.
   - Direct connection of both nodes to the Production Cloud Backend.
2. User Visual Benchmarks:
   - Splash Screen (`media_1789280907273.png`): Stark white, Alpha mesh, bold title, DeployMate powered by logo, auto-transition.
   - Founder Access Gate (`media_1789280951800.png`): 02 // ACCESS GATE, STAGE 2/3, Touch ID square, 4 PIN boxes, Keypad with [AUTO], [0], [⌫], Instant Founder Biometric Unlock.

YOUR SENIOR REVIEW TASKS:
1. Senior Critique & Threat Modeling:
   - Interception of QR code on shared screens / video calls (require short confirmation code / verification hash match on both devices).
   - Replay attack mitigation (cryptographic nonces, 120s TTL, single-use tickets).
   - Local network vs USB ADB vs Cloud Relay routing precedence.
   - Offline behavior: What happens if internet drops but Mac and phone are on same LAN or connected via USB cable?
2. Formal State Machine Invariants:
   - Prove that Mobile app cannot access protected screens without completing enrollment or authentication.
   - Define exact transitions: `SPLASH` -> `ENROLLMENT` (first-run) -> `QR_SCAN_BRIDGE` -> `ACCESS_GATE` (returning) -> `SYNC` -> `DASHBOARD`.
3. Screen Design Matrix:
   - Ratify 4 Mac Desktop screens (M-01 to M-04).
   - Ratify 15 Mobile Companion screens (including new Enrollment and QR Scan Bridge).
4. Section 14.2 Canonical Markdown:
   - Author the authoritative, binding Section 14.2 text for `docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md`.
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
        "360s",
    ]

    try:
        res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=WORKSPACE_ROOT, timeout=420)
        if res.returncode != 0:
            print(f"Claude Opus Round 2 Error: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        raw_stdout = res.stdout.strip()
        data = json.loads(raw_stdout)

        # Check structured_output or parse from response
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

        with open(WORKSPACE_ROOT / "testscript" / "round2_opus_ecosystem_ratification.json", "w") as out_f:
            json.dump(ratification, out_f, indent=2)
        print("✅ [ROUND 2 COMPLETE] Claude Opus architectural ratification received.")
        return ratification
    finally:
        Path(schema_file).unlink(missing_ok=True)


def main():
    mobile_screens_file = WORKSPACE_ROOT / "docs" / "architecture" / "ALPHABRAIN_MOBILE_SCREENS.md"
    mobile_screens_summary = mobile_screens_file.read_text() if mobile_screens_file.exists() else "Mobile screens catalog"

    context = {
        "mobile_screens_summary": mobile_screens_summary
    }

    r1_file = WORKSPACE_ROOT / "testscript" / "round1_gemini_ecosystem_proposal.json"
    if r1_file.exists():
        print("⚡ [ROUND 1 CACHED] Loading existing Gemini Pro proposal from file...")
        with open(r1_file) as f:
            r1_proposal = json.load(f)
    else:
        # Execute Round 1: Gemini 3.1 Pro High
        r1_proposal = run_round_1_gemini(context)

    # Execute Round 2: Claude Opus 4.6 Thinking
    r2_ratification = run_round_2_opus(context, r1_proposal)

    # Append ratified Section 14.2 to SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md
    directive_file = WORKSPACE_ROOT / "docs" / "architecture" / "SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md"
    section_14_2_text = r2_ratification.get("section_14_2_canonical_markdown", "")

    if section_14_2_text and directive_file.exists():
        existing_text = directive_file.read_text()
        if "### 14.2 AlphaBrain Mac App & Mobile Companion QR Synchronization Architecture" not in existing_text:
            updated_text = existing_text.rstrip() + "\n\n---\n\n" + section_14_2_text + "\n"
            directive_file.write_text(updated_text)
            print("📜 [DIRECTIVE UPDATED] Section 14.2 successfully appended to docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md")

    print("\n🎉 [2-ROUND SENIOR PLANNING DEBATE CONCLUDED SUCCESSFULLY]")


if __name__ == "__main__":
    main()
