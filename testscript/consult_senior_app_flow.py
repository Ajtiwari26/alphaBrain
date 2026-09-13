"""Consult Claude Opus 4.6 (Thinking) on the canonical Founder Companion App Flow.

Defines state machine transitions, animation standards, and UX feel specifications.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")


def consult_senior():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "flow_verdict": {
                "type": "string",
                "enum": ["READY_FOR_FLOW", "REPAIRS_REQUIRED"],
            },
            "state_machine_spec": {
                "type": "string",
                "description": "Step-by-step state machine from cold boot to hot command center",
            },
            "animation_and_ux_directive": {
                "type": "string",
                "description": "Concrete CSS/Tailwind animations, transitions, and tactile feedback standards",
            },
            "implementation_steps": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["flow_verdict", "state_machine_spec", "animation_and_ux_directive", "implementation_steps"],
        "additionalProperties": False,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        schema_file = f.name

    prompt = """You are Claude Opus 4.6 (Thinking), Supreme Lead Architect for AlphaBrain.

CRITICAL USER FEEDBACK ON FOUNDER COMPANION APP:
"ui is there but no ux no aniimation no feel no proper flow is mainatained directly showing hoemscreen instead of splash screen then authentication then bridge then everything and also still somethings seems to be mock or something no proper way to correc the flow of the app , ask senior for flow of the app and is app is ready for the flow"

CONTEXT:
- The app currently has 14 Locomotive Stark White screens implemented in `alphabrain_app/src/screens/`.
- However, `App.tsx` was initializing directly to `overview` (Command Center), completely bypassing:
  1. `SplashScreen` (Brand symbol, boot sequence)
  2. `AuthScreen` (Founder access verification)
  3. `InstanceSyncScreen` (Live USB ADB ping to backend on port 8000 for device 10BF5P2AZF0010T)
- Furthermore, screens swap instantaneously with zero CSS animations, no tactile button feel, and no smooth transition choreography.
- The live backend is running on `http://localhost:8000` via ADB reverse `tcp:8000 tcp:8000` to physical device `10BF5P2AZF0010T`.

ARCHITECTURAL QUESTIONS FOR SENIOR:
1. What is the canonical, binding state machine lifecycle for the Founder Companion app?
   - Define exact transitions: `BOOTING_SPLASH` -> `FOUNDER_AUTH` -> `INSTANCE_SYNC` -> `COMMAND_CENTER` (hot session).
   - How should session persistence and drawer navigation work once authenticated?
2. What are the specific animation and tactile feel requirements to turn this from a static wireframe into an ultra-high-end executive companion app?
   - Page transitions (slide, fade, scale).
   - Micro-interactions (haptic spring, active press states, pulse indicators).
3. Is the existing architecture and live backend ready for this flow?
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
        res = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            timeout=360,
        )
        if res.returncode != 0:
            print(f"Error: {res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        data = json.loads(res.stdout)
        struct = data.get("structured_output") or data
        print(json.dumps(struct, indent=2))
    finally:
        Path(schema_file).unlink(missing_ok=True)


if __name__ == "__main__":
    consult_senior()
