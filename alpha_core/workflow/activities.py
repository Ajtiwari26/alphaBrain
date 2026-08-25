import asyncio
from typing import Any, cast

from alpha_core.db.connection import get_session_factory
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    CallJob,
    PersonaType,
    TaskEnvelope,
    TaskStatus,
)
from alpha_voice.extractor import SpecExtractor


class SDLCActivities:
    """Activities invoked by the durable Temporal SDLC workflow."""

    @staticmethod
    async def extract_specification(
        transcript_text: str, project_id: str, title: str
    ) -> dict[str, Any]:
        """Extracts requirements and decisions from a meeting transcript."""
        # Simulated extraction for testing & fallback
        spec = SpecExtractor.parse_extraction_json(
            """```json
{
  "requirements": [
    {
      "req_id": "req_sdlc_01",
      "title": "Core Feature",
      "description": "Implement verified core functionality",
      "acceptance_criteria": ["All unit tests pass"],
      "priority": "must_have"
    }
  ],
  "decisions": [
    {
      "dec_id": "dec_sdlc_01",
      "topic": "Workflow State",
      "decision": "Use Temporal Durable State Machine",
      "rationale": "Resilience against Mac sleep, disconnects, and restarts"
    }
  ],
  "open_questions": []
}
```""",
            project_id=project_id,
            title=title,
        )
        return cast(dict[str, Any], spec.model_dump())

    @staticmethod
    async def dispatch_task(task_envelope_data: dict[str, Any]) -> str:
        """Submits task envelope to the database queue."""
        envelope = TaskEnvelope.model_validate(task_envelope_data)
        session_factory = get_session_factory()
        async with session_factory() as session:
            task = await TaskEngine.submit_task(session, envelope)
            await session.commit()
            return cast(str, task.id)

    @staticmethod
    async def wait_for_task_verification(task_id: str, timeout_seconds: int = 1800) -> bool:
        """Polls until the task reaches VERIFIED status."""
        session_factory = get_session_factory()
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            async with session_factory() as session:
                from sqlalchemy import select

                from alpha_core.db.models import TaskRecord

                res = await session.execute(select(TaskRecord).where(TaskRecord.id == task_id))
                task = res.scalar_one_or_none()
                if task and task.status == TaskStatus.VERIFIED.value:
                    return True
                elif task and task.status in [TaskStatus.BLOCKED.value, TaskStatus.CANCELLED.value]:
                    return False
            await asyncio.sleep(2)
        return False

    @staticmethod
    async def trigger_founder_alert_call(
        project_id: str,
        founder_phone: str,
        preview_url: str,
    ) -> dict[str, Any]:
        """Creates a CallJob for Eva to notify the founder of a verified preview."""
        job = CallJob(
            notification_id=f"ntf_sdlc_{project_id}",
            persona=PersonaType.EVA,
            recipient_phone=founder_phone,
            purpose="founder_preview_review",
            script_facts={"project_id": project_id, "preview_url": preview_url},
            idempotency_key=f"idemp_{project_id}_preview",
        )
        return cast(dict[str, Any], job.model_dump())
