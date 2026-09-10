"""
Tests for SP2 Research Agent output schema compliance and parsing.
"""

from pathlib import Path
import json

import pytest

from alpha_core.planning.research_agent import ResearchAgent, ResearchConsensusError
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_protocol.planning import ResearchSnapshot

def test_research_agent_schema_parsing(monkeypatch, tmp_path):
    queue = TaskTriageQueue(db_path=str(tmp_path / "triage.db"))
    
    # Create a dummy task
    task_id = "tsk_test_agent"
    envelope = {
        "project_id": "test_project",
        "repo": "test_repo",
        "base_commit": "1234567890abcdef1234567890abcdef12345678",
        "title": "Test Task",
        "summary": "Implement rate limiting"
    }
    # Hack the queue to just return our envelope without full enqueue
    def mock_get_task(tid):
        if tid == task_id:
            return {"envelope": envelope, "status": "pending_review"}
        return None
    
    monkeypatch.setattr(queue, "get_task", mock_get_task)

    agent = ResearchAgent(queue)

    def mock_invoke_agy(model, prompt, schema, timeout_seconds=900):
        return {
            "sources": [
                {
                    "source_type": "url",
                    "reference": "https://redis.io/docs/manual/patterns/rate-limit/",
                    "publisher": "Redis",
                    "excerpts": ["Use INCR and EXPIRE for basic rate limiting"],
                    "supported_claim_ids": ["redis_rate_limit"]
                }
            ],
            "unresolved_questions": ["What is the exact load expected?"]
        }
        
    monkeypatch.setattr(agent, "_invoke_agy_research", mock_invoke_agy)

    snapshot = agent.execute_research_phase(task_id)
    
    assert isinstance(snapshot, ResearchSnapshot)
    assert snapshot.task_id == task_id
    assert snapshot.project_id == "test_project"
    assert len(snapshot.sources) == 1
    
    src = snapshot.sources[0]
    assert src.reference == "https://redis.io/docs/manual/patterns/rate-limit/"
    assert src.content_digest is not None
    assert len(src.content_digest) == 64
    
    assert snapshot.unresolved_questions == ["What is the exact load expected?"]
