"""
AlphaBrain Senior Planning Engine
=================================
Coordinates the Upfront Senior Planning Gate (SP3).
Executes a 2-Round Debate between Gemini 3.1 Pro (Draft) and Claude Opus 4.6 (Critique).
Emits the cryptographically bound PlanningAttestation and PlanBlueprint.
"""

import hashlib
import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_protocol.planning import PlanAssessment, PlanBlueprint, PlanningAttestation, ResearchSnapshot
from alpha_core.planning.research_broker import ResearchBroker

logger = logging.getLogger("alphabrain.planning.senior_planning_engine")


class PlanningConsensusError(Exception):
    """Raised when models cannot agree on a plan."""
    pass


class SeniorPlanningEngine:
    def __init__(
        self,
        queue: TaskTriageQueue,
        research_broker: ResearchBroker,
        agy_bin: Path | None = None,
        signing_secret: str | bytes | None = None,
        key_id: str = "alpha_production_v1",
    ) -> None:
        import os

        self.queue = queue
        self.broker = research_broker
        self.agy_bin = agy_bin or (Path.home() / ".local" / "bin" / "agy")
        self.key_id = key_id
        self.signing_secret = signing_secret or os.environ.get(f"ALPHA_SIGNING_SECRET_{key_id}")

    def _invoke_agy_planning(
        self,
        model: str,
        prompt: str,
        schema: dict,
        timeout_seconds: int = 600,
    ) -> dict:
        """Invokes AGY for a planning step."""
        if not self.agy_bin.exists():
            raise RuntimeError(f"AGY executable not found at {self.agy_bin}")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt)
            prompt_file = f.name
            
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            schema_file = f.name

        try:
            cmd = [
                str(self.agy_bin),
                "--model",
                model,
                "--mode",
                "plan",
                "--output-format",
                "json",
                "--input-format",
                "text",
                "--json-schema",
                schema_file,
                "--print-timeout",
                f"{timeout_seconds}s",
            ]
            
            logger.info("Invoking planning model %s...", model)
            res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout_seconds)
            
            if res.returncode != 0:
                logger.error("Planning model %s failed: %s", model, res.stderr)
                raise RuntimeError(f"Model invocation failed: {res.stderr}")
                
            # Parse last JSON object from stdout
            lines = res.stdout.strip().splitlines()
            for line in reversed(lines):
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            
            # Fallback
            return json.loads(res.stdout.strip())
            
        finally:
            Path(prompt_file).unlink(missing_ok=True)
            Path(schema_file).unlink(missing_ok=True)

    def execute_planning_phase(
        self,
        task_id: str,
        research_snapshot: ResearchSnapshot,
    ) -> tuple[PlanningAttestation, PlanBlueprint]:
        """
        Runs the 2-Round Planning Debate and produces the Attestation.
        """
        if not self.signing_secret:
            raise ValueError("ALPHA_SIGNING_SECRET is required to sign planning attestations.")

        task = self.queue.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found in queue.")

        request_json = json.dumps(research_snapshot.model_dump(), indent=2)

        # -------------------------------------------------------------------
        # Round 1: Gemini 3.1 Pro High Drafts the Plan
        # -------------------------------------------------------------------
        draft_schema = {
            "type": "object",
            "properties": {
                "requirements": {"type": "array", "items": {"type": "string"}},
                "alternatives_considered": {"type": "array", "items": {"type": "string"}},
                "chosen_design": {"type": "string"},
                "file_scope": {"type": "array", "items": {"type": "string"}},
                "token_budgets": {"type": "object", "additionalProperties": {"type": "integer"}}
            },
            "required": ["requirements", "alternatives_considered", "chosen_design", "file_scope"]
        }

        pro_prompt = f"""
You are Gemini 3.1 Pro High, Senior Architect.
Draft a comprehensive implementation plan for the following task based on the research snapshot.

Task Objective: {task.get("objective", "")}
Research Snapshot:
{request_json}
"""
        try:
            pro_response = self._invoke_agy_planning("gemini-3.1-pro-high", pro_prompt, draft_schema)
        except Exception as e:
            raise PlanningConsensusError(f"Pro Draft failed: {e}")

        # Assemble the Blueprint from the draft
        blueprint = PlanBlueprint(
            task_id=task_id,
            base_sha=research_snapshot.base_sha,
            input_request_digest=research_snapshot.request_digest,
            research_snapshot_digest=hashlib.sha256(request_json.encode()).hexdigest(),
            requirements=pro_response.get("requirements", []),
            alternatives_considered=pro_response.get("alternatives_considered", []),
            chosen_design=pro_response.get("chosen_design", "No design provided"),
            file_scope=pro_response.get("file_scope", []),
            token_budgets=pro_response.get("token_budgets", {})
        )
        
        blueprint_digest = blueprint.compute_digest()

        pro_assessment = PlanAssessment(
            reviewer_principal="gemini-3.1-pro-high",
            role="drafting",
            plan_digest=blueprint_digest,
            verdict="APPROVE",
            findings="Drafted the initial plan."
        )

        # -------------------------------------------------------------------
        # Round 2: Claude Opus 4.6 Challenges the Draft
        # -------------------------------------------------------------------
        critique_schema = {
            "type": "object",
            "properties": {
                "findings": {"type": "string"},
                "verdict": {"type": "string", "enum": ["APPROVE", "REPAIR_REQUIRED", "BLOCKED"]},
            },
            "required": ["findings", "verdict"]
        }

        opus_prompt = f"""
You are Claude Opus 4.6 Thinking, Supreme Lead Architect.
Review the following Plan Blueprint drafted by Gemini 3.1 Pro High for the task.
Verify it adheres to architecture invariants, SSRF safety, and correctness.

Task Objective: {task.get("objective", "")}
Plan Blueprint:
{json.dumps(blueprint.model_dump(), indent=2)}

Decide to APPROVE, REPAIR_REQUIRED, or BLOCKED.
"""
        try:
            opus_response = self._invoke_agy_planning("claude-opus-4-6-thinking", opus_prompt, critique_schema)
        except Exception as e:
            raise PlanningConsensusError(f"Opus Critique failed: {e}")

        opus_verdict = opus_response.get("verdict", "BLOCKED")
        opus_assessment = PlanAssessment(
            reviewer_principal="claude-opus-4-6-thinking",
            role="critique",
            plan_digest=blueprint_digest,
            verdict=opus_verdict,
            findings=opus_response.get("findings", "No findings.")
        )

        if opus_verdict != "APPROVE":
            raise PlanningConsensusError(f"Opus rejected the plan: {opus_assessment.findings}")

        # -------------------------------------------------------------------
        # Emit Attestation
        # -------------------------------------------------------------------
        attestation = PlanningAttestation.create(
            task_id=task_id,
            project_id=task.get("project_id", "unknown"),
            repository_identity=task.get("repo", "unknown"),
            base_sha=research_snapshot.base_sha,
            blueprint_digest=blueprint_digest,
            pro_assessment=pro_assessment,
            opus_assessment=opus_assessment,
            secret=str(self.signing_secret),
            key_id=self.key_id
        )

        return attestation, blueprint
