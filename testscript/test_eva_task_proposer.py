"""
testscript/test_eva_task_proposer.py
Unit tests verifying Alpha Protocol TaskEnvelope generation from Eva's specifications.
"""

import pytest

from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_core.eva.task_proposer import EvaTaskProposer
from alpha_protocol.enums import AgentType, GateType


def test_build_task_envelope_success():
    proposer = EvaTaskProposer(default_repo="clientProjects/stripe-service", default_branch="main")

    spec = ExtractedSpecification(
        title="Add Stripe Idempotency Key Header",
        summary="Prevent duplicate payment charges by attaching Idempotency-Key.",
        requirements=["Include Idempotency-Key header on all charge calls"],
        acceptance_criteria=["Return existing charge if key already seen"],
        allowed_paths=["stripe_client.py", "tests/test_stripe.py"],
        is_actionable=True,
        confidence_score=0.9,
    )

    envelope = proposer.build_task_envelope(spec=spec, project_id="prj_stripe_001")

    assert envelope.task_id.startswith("tsk_eva_")
    assert envelope.project_id == "prj_stripe_001"
    assert envelope.objective == "Add Stripe Idempotency Key Header"
    assert "Idempotency-Key" in (envelope.detailed_instructions or "")
    assert envelope.allowed_paths == ["stripe_client.py", "tests/test_stripe.py"]
    assert GateType.UNIT_TEST in envelope.acceptance_plan.required_gates
    assert GateType.LINT in envelope.acceptance_plan.required_gates
    assert envelope.preferred_agent == AgentType.ANTIGRAVITY
    assert envelope.requires_approval is True


def test_build_task_envelope_rejects_non_actionable():
    proposer = EvaTaskProposer()

    spec = ExtractedSpecification(
        title="Casual Chat",
        summary="Greeting only",
        is_actionable=False,
    )

    with pytest.raises(ValueError, match="Cannot propose a task"):
        proposer.build_task_envelope(spec=spec, project_id="prj_test")
