"""Consult Claude Opus 4.6 (Thinking) for the Founder Companion App Flow, Enrollment, and System Design.

Ratifies Section 14.2 in docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")


def consult_senior_lifecycle_design():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["APPROVED", "REPAIRS_REQUIRED"],
            },
            "flow_architecture_summary": {
                "type": "string",
                "description": "Executive summary of the multi-stage onboarding, enrollment, and return-founder state machine",
            },
            "enrollment_specification": {
                "type": "string",
                "description": "Detailed specification of First-Run PIN Creation, Confirmation, and Biometric Registration (Stage 02A)",
            },
            "access_gate_specification": {
                "type": "string",
                "description": "Detailed specification of Returning Founder Access Gate (Stage 02B) matching media_1789280951800.png",
            },
            "state_machine_matrix": {
                "type": "string",
                "description": "State transition table across Splash, Enrollment, Access Gate, Instance Sync, and Command Center",
            },
            "storage_and_security_design": {
                "type": "string",
                "description": "Cryptographic hashing, salt, secure storage key schema, and session management",
            },
            "section_14_2_markdown": {
                "type": "string",
                "description": "Complete markdown text of Section 14.2 ready for docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md",
            },
        },
        "required": [
            "verdict",
            "flow_architecture_summary",
            "enrollment_specification",
            "access_gate_specification",
            "state_machine_matrix",
            "storage_and_security_design",
            "section_14_2_markdown",
        ],
        "additionalProperties": False,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = """You are Claude Opus 4.6 (Thinking), Supreme Lead Architect for AlphaBrain.

CRITICAL USER REQUIREMENT & PROMPT:
"and before founder access where is the face or pin creation it is not there give senior the task for formulating the proper flow plan and system design"

USER IMAGES & REFERENCE ASSETS:
1. Splash Screen Reference (media_1789280907273.png):
   - Stark pure white #FFFFFF background.
   - AlphaBrain 3D neural wireframe mesh symbol (/alpha_symbol.svg).
   - Heavy bold "AlphaBrain" title.
   - Near bottom: "POWERED BY" + DeployMate constellation logo (/deploymate_logo.png).
   - 2.0-second non-blocking auto-transition to next stage.
   - Zero buttons, zero top header bar, zero debug logs.

2. Founder Access Reference (media_1789280951800.png):
   - Stage tag: 02 // ACCESS GATE with red pill badge STAGE 2/3.
   - Title: Founder Access.
   - Horizontal rule separator.
   - Center Biometric square box: Face / Touch ID scanner icon + label TOUCH ID.
   - 4 square PIN digit boxes: [ ] [ ] [ ] [ ].
   - Monospace label: ENTER 4-DIGIT PIN OR TAP TOUCH ID.
   - Keypad: Rows [1,2,3], [4,5,6], [7,8,9], and bottom row:
     [ AUTO ] (in red text) | [ 0 ] | [ ⌫ ] (backspace).
   - Bottom horizontal rule separator.
   - Full-width tactile button at bottom: Instant Founder Biometric Unlock           ↗.

THE CORE ARCHITECTURAL PROBLEM:
The user rightly pointed out that on a fresh install or cold setup, the founder has NEVER created a PIN or enrolled biometrics. Dropping directly into the "Founder Access" unlock screen with no enrolled credentials makes no sense.

YOUR TASK:
Formulate the definitive, binding System Design and Flow Architecture covering:
1. Initial Install / Fresh Cold Start vs Returning Founder:
   - How does the client detect credential presence? (e.g. alpha_founder_credentials_v1 in secure storage).
   - Stage 01: Clean Splash Screen (2.0s auto handoff).
   - Stage 02A: Founder Enrollment (First Run Only):
     * Step 1: Create 4-Digit Master PIN (02 // FOUNDER ENROLLMENT - STAGE 1/3 - "Create Master PIN").
     * Step 2: Confirm 4-Digit Master PIN ("Confirm Master PIN" - with tactile shake animation if mismatch).
     * Step 3: Biometric Touch/Face ID Enablement prompt.
     * Persistence: Storing credential payload with PBKDF2/SHA-256 salt & hash.
   - Stage 02B: Founder Access Gate (Returning Founder):
     * The exact UI from media_1789280951800.png.
     * Verification of 4-digit PIN against stored hash.
     * Touch ID box tap triggers instant biometric check.
     * [AUTO] button behavior (in dev/debug: instant valid PIN entry for rapid operator testing; in prod: configurable or hidden).
     * Bottom "Instant Founder Biometric Unlock" triggers biometric prompt.
   - Stage 03: Instance Sync (03 // HARDWARE BRIDGE - STAGE 3/3):
     * Live ping to http://localhost:8000/api/v1/mobile/overview.
     * Real-time round trip latency measurement (<10ms).
     * Validating host health (CPU, RAM) and connected USB device 10BF5P2AZF0010T.
   - Stage 04: Command Center (Fleet Dashboard):
     * Unlocks top header bar (AlphaBrain DEPLOYMATE • LIVE), hamburger drawer with 14 screens, bottom navigation.
   - Replay & Reset Flows:
     * Session Lock (returns to Stage 02B Access Gate).
     * Factory Wipe / Reset Credentials (wipes stored PIN, returns to Stage 02A Enrollment).

Format your response matching the requested JSON schema, including the exact Markdown for Section 14.2 to be added to docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md.
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
        "300s",
    ]

    try:
        print("[Consulting Claude Opus 4.6 (Thinking)...]")
        res = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            timeout=360,
        )
        if res.returncode != 0:
            print(f"Error from Opus agy: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        data = json.loads(res.stdout)
        struct = data.get("structured_output") or data
        output_path = WORKSPACE_ROOT / "testscript" / "opus_lifecycle_decision.json"
        with open(output_path, "w") as out_f:
            json.dump(struct, out_f, indent=2)
        print(f"Successfully received Senior Architecture from Claude Opus. Saved to {output_path}")
    finally:
        Path(schema_file).unlink(missing_ok=True)


if __name__ == "__main__":
    consult_senior_lifecycle_design()
