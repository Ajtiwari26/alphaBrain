import json
import re

from alpha_protocol import (
    Decision,
    OpenQuestion,
    Requirement,
    SpecVersion,
)


class SpecExtractor:
    """Extracts structured requirements, decisions, and open questions from conversation transcripts."""

    EXTRACTION_PROMPT = """
You are an expert technical specification analyst.
Analyze the following transcript of a client/founder meeting or call.
Extract:
1. Specific, unambiguous technical requirements with acceptance criteria.
2. Architecture and product decisions made during the conversation.
3. Unresolved open questions or items requiring further clarification.

Return STRICT JSON matching the following schema:
{
  "requirements": [
    {
      "req_id": "req_1",
      "title": "Short title",
      "raw_quote": "Direct quote from transcript",
      "description": "Clear requirement description",
      "acceptance_criteria": ["Criteria 1", "Criteria 2"],
      "priority": "must_have|should_have|nice_to_have"
    }
  ],
  "decisions": [
    {
      "dec_id": "dec_1",
      "topic": "Topic name",
      "decision": "What was decided",
      "rationale": "Why it was chosen"
    }
  ],
  "open_questions": [
    {
      "question_id": "q_1",
      "question": "The question text",
      "context": "Context from conversation",
      "owner": "founder|client"
    }
  ]
}
"""

    @classmethod
    def parse_extraction_json(cls, raw_json_text: str, project_id: str, title: str) -> SpecVersion:
        """Parses model extraction JSON output into a typed SpecVersion object."""
        # Strip markdown fences if present
        clean_text = re.sub(r"^```json\s*", "", raw_json_text.strip(), flags=re.MULTILINE)
        clean_text = re.sub(r"\s*```$", "", clean_text.strip(), flags=re.MULTILINE)

        data = json.loads(clean_text)

        reqs = [Requirement(**item) for item in data.get("requirements", [])]
        decs = [Decision(**item) for item in data.get("decisions", [])]
        questions = [OpenQuestion(**item) for item in data.get("open_questions", [])]

        return SpecVersion(
            version=1,
            project_id=project_id,
            title=title,
            summary=f"Extracted specification with {len(reqs)} requirements and {len(decs)} decisions.",
            requirements=reqs,
            decisions=decs,
            open_questions=questions,
        )
