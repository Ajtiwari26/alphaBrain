"""
alpha_core/eva/queue_producer.py
Connects Eva's specification extraction pipeline directly to the TaskTriageQueue.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 6 - P9 Constitution)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_core.eva.task_proposer import EvaTaskProposer
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_protocol.task import TaskEnvelope

logger = logging.getLogger("alphabrain.eva.producer")


class EvaQueueProducer:
    """
    Producer adapter that takes an extracted meeting specification,
    constructs an immutable provenance record, builds a TaskEnvelope,
    and inserts it into the TaskTriageQueue with status PENDING_REVIEW.
    """

    def __init__(
        self,
        queue: TaskTriageQueue,
        task_proposer: EvaTaskProposer | None = None,
    ) -> None:
        self.queue = queue
        self.task_proposer = task_proposer or EvaTaskProposer()

    @staticmethod
    def compute_content_hash(
        title: str,
        acceptance_criteria: list[str],
        allowed_paths: list[str],
    ) -> str:
        """Computes a canonical SHA-256 hash representing the semantic intent of the task."""
        payload = {
            "title": title.strip().lower(),
            "criteria": sorted([c.strip().lower() for c in acceptance_criteria]),
            "paths": sorted([p.strip().lower() for p in allowed_paths]),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def enqueue_specification(
        self,
        spec: ExtractedSpecification,
        project_id: str,
        meeting_id: str,
        transcript_excerpt: str,
        speaker_id: str | None = None,
        extraction_model: str = "gemini-3.1-pro-high",
        extraction_confidence: float = 1.0,
        eva_session_id: str = "eva_livekit_consumer",
        repo: str | None = None,
        base_commit: str | None = None,
    ) -> tuple[str, TaskEnvelope, TaskProvenance]:
        """
        Converts an extracted specification into an Alpha Protocol TaskEnvelope and
        TaskProvenance record, inserting it into the triage queue.
        """
        if not spec.is_actionable:
            raise ValueError(
                f"Specification '{spec.title}' is marked non-actionable; skipping enqueue."
            )

        # 1. Build TaskEnvelope
        envelope = self.task_proposer.build_task_envelope(
            spec=spec,
            project_id=project_id,
            repo=repo,
            base_commit=base_commit,
        )

        # 2. Serialize envelope to dict for queue storage
        envelope_dict: dict[str, Any] = (
            envelope.model_dump(mode="json") if hasattr(envelope, "model_dump") else envelope.dict()
        )
        envelope_dict["acceptance_criteria"] = spec.acceptance_criteria
        envelope_dict["title"] = spec.title

        # 3. Compute canonical content hash
        content_hash = hashlib.sha256(
            json.dumps(envelope_dict, sort_keys=True, separators=(",", ":"), default=str).encode(
                "utf-8"
            )
        ).hexdigest()

        # 4. Create immutable provenance record
        provenance = TaskProvenance(
            meeting_id=meeting_id,
            speaker_id=speaker_id,
            utterance_timestamp=time.time(),
            transcript_excerpt=transcript_excerpt,
            extraction_model=extraction_model,
            extraction_confidence=extraction_confidence,
            eva_session_id=eva_session_id,
            created_at=time.time(),
            content_hash=content_hash,
        )

        # 5. Enqueue with status = PENDING_REVIEW (Law 1: No Direct Path)
        task_id = self.queue.enqueue_task(
            task_id=envelope.task_id,
            envelope=envelope_dict,
            provenance=provenance,
            initial_status=TriageStatus.PENDING_REVIEW,
        )

        logger.info(
            "Eva successfully enqueued task %s (%s) from meeting %s",
            task_id,
            spec.title,
            meeting_id,
        )

        return task_id, envelope, provenance
