"""
alpha_core/eva/spec_extractor.py
Structured specification extraction from meeting dialogue using Gemini models.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 4.2)
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

from google import genai

from alpha_core.config import settings

logger = logging.getLogger("alpha_core.eva.spec_extractor")


@dataclass
class ExtractedSpecification:
    """A concrete engineering specification extracted from meeting dialogue."""

    title: str
    summary: str
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    required_gates: list[str] = field(default_factory=lambda: ["unit_test", "lint"])
    confidence_score: float = 0.0
    is_actionable: bool = False
    raw_response: dict[str, Any] = field(default_factory=dict)


class EvaSpecificationExtractor:
    """Extracts structured specifications and engineering tasks from meeting transcripts."""

    EXTRACTION_PROMPT = """
You are Eva, the autonomous Lead Engineering CTO at DeployMate.
Analyze the following meeting transcript between Founder and Client.
Determine if the dialogue describes an actionable software feature, bug fix, or technical improvement.

CRITICAL RULES:
1. If the dialogue is merely small talk, greetings, administrative scheduling, or vague chatter, set "is_actionable" to false and return empty requirements.
2. Only set "is_actionable" to true if there is a concrete, implementable engineering request.
3. Extract precise acceptance criteria and identify likely files or directories to touch (allowed_paths).
4. REPOSITORY CONTEXT: The codebase consists of `alpha_core/`, `alpha_worker/`, `alpha_protocol/`, and `testscript/`. All `allowed_paths` must strictly use these real paths (e.g. `alpha_core/`, `alpha_worker/`, `testscript/`), never invent imaginary directories.
5. Output MUST be valid JSON adhering strictly to the schema below.

JSON SCHEMA:
{
  "is_actionable": boolean,
  "confidence_score": float (between 0.0 and 1.0),
  "title": string,
  "summary": string,
  "requirements": [string],
  "acceptance_criteria": [string],
  "allowed_paths": [string],
  "required_gates": ["unit_test", "lint", "typecheck"]
}
"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.8-flash-high",
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model
        self.agy_bin = settings.ANTIGRAVITY_CLI_BIN
        self.client: genai.Client | None = None

    def _call_agy(self, prompt: str) -> str | None:
        """Invokes AGY CLI using the active Google Cloud Code account."""
        if not self.agy_bin.is_file() or not (self.agy_bin.stat().st_mode & 0o111):
            return None
        cmd = [
            str(self.agy_bin),
            "-p",
            prompt,
            "--model",
            self.model,
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            if res.returncode != 0:
                logger.warning(
                    "AGY extraction returned non-zero code %d: %s",
                    res.returncode,
                    res.stderr,
                )
                return None
            return res.stdout.strip()
        except Exception as e:
            logger.warning("AGY extraction execution error: %s", e)
            return None

    @staticmethod
    def _parse_json_payload(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        res = json.loads(text)
        return dict(res) if isinstance(res, dict) else {}

    def extract_from_transcript(
        self,
        formatted_transcript: str,
    ) -> ExtractedSpecification | None:
        """Parses dialogue and returns an ExtractedSpecification via AGY active account."""
        if not formatted_transcript or not formatted_transcript.strip():
            return None

        prompt = (
            f"{self.EXTRACTION_PROMPT}\n\n"
            f"MEETING TRANSCRIPT:\n{formatted_transcript.strip()}\n\n"
            f"Provide JSON response only:"
        )

        parsed: dict[str, Any] | None = None

        # 1. Primary: Use AGY CLI via active Google Cloud Code account (free Pro quota)
        raw_text = self._call_agy(prompt)
        if raw_text:
            try:
                parsed = self._parse_json_payload(raw_text)
            except Exception as e:
                logger.warning("Failed to parse AGY JSON response: %s", e)

        # 2. Secondary fallback: Use GenAI client only if AGY failed or is unavailable
        if parsed is None and self.api_key:
            try:
                if self.client is None:
                    self.client = genai.Client(api_key=self.api_key)
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                )
                text = response.text or ""
                parsed = json.loads(text)
            except Exception as e:
                logger.error("Failed to extract specification via fallback API: %s", e)
                return None

        if not parsed:
            logger.error("Could not obtain specification from AGY or fallback API.")
            return None

        is_actionable = bool(parsed.get("is_actionable", False))
        confidence = float(parsed.get("confidence_score", 0.0))

        if not is_actionable or confidence < 0.6:
            return ExtractedSpecification(
                title=parsed.get("title", "Non-actionable dialogue"),
                summary=parsed.get("summary", ""),
                is_actionable=False,
                confidence_score=confidence,
                raw_response=parsed,
            )

        return ExtractedSpecification(
            title=str(parsed.get("title", "Proposed Feature")),
            summary=str(parsed.get("summary", "")),
            requirements=list(parsed.get("requirements", [])),
            acceptance_criteria=list(parsed.get("acceptance_criteria", [])),
            allowed_paths=list(parsed.get("allowed_paths", [])),
            required_gates=list(parsed.get("required_gates", ["unit_test", "lint"])),
            confidence_score=confidence,
            is_actionable=True,
            raw_response=parsed,
        )
