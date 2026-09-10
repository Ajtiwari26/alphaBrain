"""
AlphaBrain Autonomous Research Agent
====================================
Uses AGY CLI with web search and GitHub MCP to research open-source tools
and alternatives for a given task envelope, generating a ResearchSnapshot.
"""

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_protocol.planning import ResearchSnapshot, SourceEvidence, request_digest

logger = logging.getLogger("alphabrain.planning.research_agent")


class ResearchConsensusError(Exception):
    """Raised when research fails or is blocked."""
    pass


class ResearchAgent:
    def __init__(
        self,
        queue: TaskTriageQueue,
        agy_bin: Path | None = None,
    ) -> None:
        self.queue = queue
        self.agy_bin = agy_bin or (Path.home() / ".local" / "bin" / "agy")

    @staticmethod
    def _parse_response(stdout: str) -> dict[str, Any]:
        """Accept one JSON document, optionally AGY's structured_output envelope."""
        def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate planning response key")
                result[key] = value
            return result

        try:
            data = json.loads(stdout, object_pairs_hook=unique_pairs)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode AGY JSON output: {e}\nOutput was: {stdout[:500]}") from e

        if not isinstance(data, dict):
            raise ValueError("AGY response must be an object")
        if data.get("is_error") is True:
            raise ValueError(f"AGY reported planning failure: {data.get('error', 'Unknown error')}")

        result = data.get("structured_output", data)
        if not isinstance(result, dict):
            raise ValueError("AGY structured_output must be an object")
        return result

    def _invoke_agy_research(
        self,
        model: str,
        prompt: str,
        schema: dict,
        timeout_seconds: int = 900,
    ) -> dict:
        """Invokes AGY for a research step."""
        if not self.agy_bin.exists():
            raise RuntimeError(f"AGY executable not found at {self.agy_bin}")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            schema_file = f.name

        try:
            # Note: We do NOT use --mode plan here, so that tools are enabled.
            cmd = [
                str(self.agy_bin),
                "--model",
                model,
                "--output-format",
                "json",
                "--input-format",
                "text",
                "--json-schema",
                schema_file,
                "--print-timeout",
                f"{timeout_seconds}s",
            ]
            if "claude" not in model.lower():
                cmd.extend(["--effort", "high"])

            logger.info("Invoking research model %s...", model)

            # Hide sensitive environment vars, same as planner
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(
                    (
                        "ALPHA_",
                        "ALPHABRAIN_",
                        "DATABASE_",
                        "SUPABASE_",
                        "PLIVO_",
                        "LIVEKIT_",
                        "WORKER_",
                    )
                )
            }

            # Use subprocess to run the command interactively
            res = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True, timeout=timeout_seconds, env=env
            )

            if res.returncode != 0:
                logger.error("AGY stdout: %s", res.stdout)
                logger.error("AGY stderr: %s", res.stderr)
                raise RuntimeError(
                    f"Research model exited with status {res.returncode}"
                )

            return self._parse_response(res.stdout.strip())

        finally:
            Path(schema_file).unlink(missing_ok=True)

    def execute_research_phase(self, task_id: str) -> ResearchSnapshot:
        """
        Executes live agentic research and produces a ResearchSnapshot.
        """
        task = self.queue.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found in queue.")

        envelope = task["envelope"]
        project_id = envelope.get("project_id", "default")
        repo = envelope.get("repo", "local")
        base_commit = envelope.get("base_commit", "0000000000000000000000000000000000000000")
        digest = request_digest(envelope)

        research_schema = {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_type": {"type": "string", "enum": ["url", "github_mcp", "code_review_graph", "memory_graph"]},
                            "reference": {"type": "string", "description": "URL, repo path, or query used"},
                            "publisher": {"type": "string", "description": "Who published this information (e.g. GitHub, Python Docs, StackOverflow)"},
                            "excerpts": {"type": "array", "items": {"type": "string"}, "description": "Specific quotes or code blocks from the source that are relevant"},
                            "supported_claim_ids": {"type": "array", "items": {"type": "string"}, "description": "Short string IDs (e.g. 'requires_python_3_10') that this source supports"}
                        },
                        "required": ["source_type", "reference", "publisher", "excerpts", "supported_claim_ids"]
                    }
                },
                "unresolved_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Any questions that remain unanswered after research"
                }
            },
            "required": ["sources", "unresolved_questions"]
        }

        prompt = f"""
You are the AlphaBrain Senior Research Agent.
Your job is to read the incoming task envelope, identify missing knowledge, evaluate open-source alternatives, and perform deep research using your web search and GitHub MCP tools.

Task Envelope:
{json.dumps(envelope, sort_keys=True, indent=2)}

Instructions:
1. Use Web Search and GitHub MCP to find the best open-source libraries or documentation for the features requested.
2. Verify API versions and exact configurations needed for the task.
3. Once you have gathered sufficient information, return a final structured JSON matching the provided schema.
4. List the URLs, repos, or sources you found in the `sources` array. For `excerpts`, provide the precise code snippets or rules you found.
5. If there are things you could not verify (e.g. closed-source APIs without public docs), list them in `unresolved_questions`.

Remember: The output must purely be the factual findings that will later be fed to the Senior Architects (Opus/Pro) who will write the actual Plan Blueprint.
"""

        try:
            # We use gemini-3.1-pro-high for research, as it supports tools efficiently
            response = self._invoke_agy_research("gemini-3.1-pro-high", prompt, research_schema)
        except Exception as e:
            raise ResearchConsensusError(f"Research phase failed: {e}") from e

        # Construct SourceEvidence objects
        evidence_list = []
        for src in response.get("sources", []):
            # Compute a stable content_digest based on excerpts since we didn't fetch the raw bytes directly
            excerpts_text = "".join(src.get("excerpts", []))
            content_digest = hashlib.sha256(excerpts_text.encode("utf-8")).hexdigest()

            evidence = SourceEvidence(
                source_type=src.get("source_type", "url"),
                reference=src.get("reference", ""),
                publisher=src.get("publisher", ""),
                retrieval_time=time.time(),
                content_digest=content_digest,
                excerpts=src.get("excerpts", []),
                supported_claim_ids=src.get("supported_claim_ids", [])
            )
            evidence_list.append(evidence)

        # Assemble the full snapshot
        snapshot = ResearchSnapshot(
            task_id=task_id,
            project_id=project_id,
            repository_identity=repo,
            base_sha=base_commit,
            request_digest=digest,
            retrieval_time=time.time(),
            sources=evidence_list,
            unresolved_questions=response.get("unresolved_questions", [])
        )

        return snapshot
