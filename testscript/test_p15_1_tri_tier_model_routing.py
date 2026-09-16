"""
testscript/test_p15_1_tri_tier_model_routing.py
Comprehensive verification test suite for P15.1:
1. Tri-Tier Model Routing Topology (ModelTier, ExecutionStage.RESEARCH, ConfidenceScore, ComplexityGateConfig).
2. Research Broker acceleration with confidence scoring & 3-strike escalation (gemini-3.8-flash-high).
3. ComplexityGate evaluation, sensitive path boundary checks & escalation rules.
4. Cross-Provider Review Independence (Invariants I-61 & I-62), claude-sonnet-4-6 fallback, and DEGRADED_SAME_FAMILY attestation/blocking.
"""

from datetime import datetime
from unittest.mock import MagicMock

from alpha_core.planning.research_agent import (
    ResearchAgent,
    compute_research_confidence,
    route_research_query,
)
from alpha_protocol.routing import (
    ComplexityGateConfig,
    ConfidenceScore,
    DegradedSameFamilyAttestation,
    ExecutionStage,
    ModelTier,
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingRequest,
)
from alpha_worker.routing import (
    ComplexityGate,
)
from alpha_worker.senior_review_engine import (
    DEGRADED_SAME_FAMILY,
    INDEPENDENT_CROSS_PROVIDER,
    SeniorReviewEngine,
    evaluate_review_independence,
)

# ============================================================================
# Contract 1 Tests: Protocol Schemas & Tri-Tier Enums
# ============================================================================


def test_model_tier_enum_values():
    assert ModelTier.TIER_1_FAST.value == "tier_1_fast"
    assert ModelTier.TIER_2_STANDARD.value == "tier_2_standard"
    assert ModelTier.TIER_3_REASONING.value == "tier_3_reasoning"


def test_execution_stage_research():
    assert ExecutionStage.RESEARCH.value == "research"


def test_confidence_score_schema():
    conf = ConfidenceScore(score=0.92, source="test_broker", strike_count=1, signals=["test_signal"])
    assert conf.score == 0.92
    assert conf.source == "test_broker"
    assert conf.strike_count == 1
    assert conf.signals == ["test_signal"]


def test_complexity_gate_config_defaults():
    config = ComplexityGateConfig()
    assert config.tier_1_model == "gemini-3.8-flash-high"
    assert config.tier_2_model == "gemini-3.1-pro-high"
    assert config.tier_3_model_claude == "claude-opus-4-6-thinking"
    assert config.tier_3_model_fallback == "claude-sonnet-4-6"
    assert config.max_strikes_before_escalation == 3
    assert "auth" in config.sensitive_path_patterns
    assert "crypto" in config.sensitive_path_patterns


def test_degraded_same_family_attestation_schema():
    att = DegradedSameFamilyAttestation(
        round1_model="gemini-3.1-pro-high",
        round2_model="gemini-3.1-pro-high",
        fallback_reason="Claude service rate limit exhausted",
    )
    assert att.degraded_same_family is True
    assert att.independence_status == DEGRADED_SAME_FAMILY
    assert att.founder_review_required is True
    assert att.round1_model == "gemini-3.1-pro-high"
    assert isinstance(att.attested_at, datetime)


def test_routing_decision_tri_tier_fields():
    dec = RoutingDecision(
        status=RoutingDecisionStatus.SELECTED,
        model="gemini-3.8-flash-high",
        tier=ModelTier.TIER_1_FAST.value,
        confidence_score=0.95,
        degraded_same_family=False,
    )
    assert dec.status == RoutingDecisionStatus.SELECTED
    assert dec.model == "gemini-3.8-flash-high"
    assert dec.tier == "tier_1_fast"
    assert dec.confidence_score == 0.95
    assert dec.degraded_same_family is False


# ============================================================================
# Contract 2 Tests: Research Broker & 3-Strike Escalation
# ============================================================================


def test_compute_research_confidence_clear_query():
    conf = compute_research_confidence("Implement exact version 2.0 schema contract endpoint")
    assert conf.score >= 0.8
    assert "research_broker" in conf.source


def test_compute_research_confidence_ambiguous_query():
    conf = compute_research_confidence("Investigate unclear and ambiguous open question tradeoffs")
    assert conf.score < 0.8
    assert any("ambiguity_keyword" in s for s in conf.signals)


def test_compute_research_confidence_strike_penalty():
    conf_0 = compute_research_confidence("Specific RFC endpoint query", strike_count=0)
    conf_1 = compute_research_confidence("Specific RFC endpoint query", strike_count=1)
    conf_2 = compute_research_confidence("Specific RFC endpoint query", strike_count=2)
    assert conf_0.score > conf_1.score > conf_2.score


def test_route_research_query_high_confidence_acceleration():
    dec = route_research_query(
        query="Verify exact SQLite schema migration version 4",
        confidence_score=0.92,
        strike_count=0,
    )
    assert dec.model == "gemini-3.8-flash-high"
    assert dec.tier == ModelTier.TIER_1_FAST.value
    assert dec.confidence_score == 0.92
    assert "research_broker_accelerated_flash" in dec.rationale_codes


def test_route_research_query_medium_confidence_standard():
    dec = route_research_query(
        query="Investigate library architecture",
        confidence_score=0.65,
        strike_count=0,
    )
    assert dec.model == "gemini-3.1-pro-high"
    assert dec.tier == ModelTier.TIER_2_STANDARD.value
    assert "research_standard_pro" in dec.rationale_codes


def test_route_research_query_low_confidence_escalation():
    dec = route_research_query(
        query="Completely unknown proprietary protocol exploration",
        confidence_score=0.35,
        claude_budget_allowed=True,
    )
    assert dec.model == "claude-opus-4-6-thinking"
    assert dec.tier == ModelTier.TIER_3_REASONING.value
    assert "escalation_low_confidence_or_high_complexity" in dec.rationale_codes


def test_route_research_query_three_strike_escalation():
    # Regardless of base query confidence, 3 strikes must escalate to Tier 3
    dec = route_research_query(
        query="Simple clear query",
        confidence_score=0.99,
        strike_count=3,
        claude_budget_allowed=True,
    )
    assert dec.model == "claude-opus-4-6-thinking"
    assert dec.tier == ModelTier.TIER_3_REASONING.value
    assert "escalation_three_strikes_breached" in dec.rationale_codes


def test_research_agent_strike_tracking():
    mock_queue = MagicMock()
    agent = ResearchAgent(queue=mock_queue)
    task_id = "tsk_test_strike"

    dec_0 = agent.route_research_query({"task_id": task_id, "title": "Clear query"}, confidence_score=0.95)
    assert dec_0.model == "gemini-3.8-flash-high"
    assert dec_0.tier == ModelTier.TIER_1_FAST.value

    # Record 3 strikes
    agent.strikes[task_id] = 3
    dec_3 = agent.route_research_query(
        {"task_id": task_id, "title": "Clear query"},
        confidence_score=0.95,
        claude_budget_allowed=True,
    )
    assert dec_3.model == "claude-opus-4-6-thinking"
    assert dec_3.tier == ModelTier.TIER_3_REASONING.value


# ============================================================================
# Contract 3 Tests: ComplexityGate & Sensitive Path Escalation
# ============================================================================


def test_complexity_gate_low_complexity_fast_tier():
    gate = ComplexityGate()
    evaluation = gate.evaluate({
        "complexity_class": "low",
        "risk_class": "low",
        "allowed_paths": ["alpha_portal/components/Button.tsx"],
        "extraction_confidence": 0.95,
    })
    assert evaluation.target_tier == ModelTier.TIER_1_FAST.value
    assert evaluation.target_model == "gemini-3.8-flash-high"
    assert evaluation.is_escalated is False


def test_complexity_gate_medium_complexity_standard_tier():
    gate = ComplexityGate()
    evaluation = gate.evaluate({
        "complexity_class": "medium",
        "risk_class": "medium",
        "allowed_paths": ["alpha_core/api/endpoints.py"],
        "extraction_confidence": 0.75,
    })
    assert evaluation.target_tier == ModelTier.TIER_2_STANDARD.value
    assert evaluation.target_model == "gemini-3.1-pro-high"


def test_complexity_gate_sensitive_path_escalation():
    gate = ComplexityGate()
    evaluation = gate.evaluate({
        "complexity_class": "low",
        "risk_class": "low",
        "allowed_paths": ["alpha_core/auth/jwt_keys.py"],
        "extraction_confidence": 0.99,
    })
    assert evaluation.is_escalated is True
    assert evaluation.target_tier == ModelTier.TIER_3_REASONING.value
    assert any("sensitive_path" in r for r in evaluation.rationale)


def test_complexity_gate_critical_risk_escalation():
    gate = ComplexityGate()
    evaluation = gate.evaluate({
        "complexity_class": "low",
        "risk_class": "critical",
        "allowed_paths": ["frontend/index.html"],
    })
    assert evaluation.is_escalated is True
    assert evaluation.target_tier == ModelTier.TIER_3_REASONING.value
    assert "escalated_risk_critical" in evaluation.rationale


def test_complexity_gate_should_escalate():
    gate = ComplexityGate()
    assert gate.should_escalate("low", "critical") is True
    assert gate.should_escalate("high", "low") is True
    assert gate.should_escalate("low", "low", confidence_score=0.3) is True
    assert gate.should_escalate("low", "low", paths=["alpha_protocol/routing.py"]) is True
    assert gate.should_escalate("low", "low", confidence_score=0.9, paths=["readme.md"]) is False


def test_complexity_gate_escalate_routing_request():
    gate = ComplexityGate()
    req = RoutingRequest(
        project_id="prj_1",
        task_id="tsk_1",
        attempt_id="att_1",
        stage=ExecutionStage.IMPLEMENT,
        risk_class="critical",
        complexity_class="low",
    )
    escalated_req = gate.escalate_request(req)
    assert escalated_req.complexity_class == "high"


# ============================================================================
# Contract 4 Tests: Cross-Provider Review Independence (Invariants I-61 & I-62)
# ============================================================================


def test_evaluate_review_independence_helper():
    # Gemini + Claude: independent cross-provider
    indep, status = evaluate_review_independence("gemini-3.1-pro-high", "claude-opus-4-6-thinking")
    assert indep is True
    assert status == INDEPENDENT_CROSS_PROVIDER

    indep2, status2 = evaluate_review_independence("gemini-3.1-pro-high", "claude-sonnet-4-6")
    assert indep2 is True
    assert status2 == INDEPENDENT_CROSS_PROVIDER

    # Gemini + Gemini: degraded same-family
    indep3, status3 = evaluate_review_independence("gemini-3.1-pro-high", "gemini-3.1-pro-high")
    assert indep3 is False
    assert status3 == DEGRADED_SAME_FAMILY


def test_senior_review_engine_claude_sonnet_fallback(monkeypatch, tmp_path):
    """
    Validates Invariant I-61:
    When claude-opus-4-6-thinking fails, engine falls back to claude-sonnet-4-6,
    maintaining cross-provider independence (INDEPENDENT_CROSS_PROVIDER).
    """
    mock_queue = MagicMock()
    # Mock task completed and gates passed
    mock_queue.get_task.return_value = {
        "status": "completed",
        "branch_name": "alpha/tsk_test",
        "worktree_path": str(tmp_path),
        "provenance": {
            "lease_metadata": {"attempt_id": "att_1", "worker_id": "worker_1"}
        },
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "worker_1",
            "result_sha": "a" * 40,
        },
        "envelope": {"base_commit": "b" * 40},
    }

    engine = SeniorReviewEngine(
        queue=mock_queue,
        signing_secret="test_secret_key_value_32_bytes_len",
        key_id="alpha_production_v1",
    )

    # Stub git checks
    monkeypatch.setattr(engine, "get_task_diff", lambda task: "diff --git a/f b/f")
    def mock_git(cmd, **kwargs):
        if "status" in cmd:
            return ""
        if "HEAD^{tree}" in cmd:
            return "c" * 40
        return "a" * 40

    monkeypatch.setattr("subprocess.check_output", mock_git)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stdout=""))
    monkeypatch.setattr("alpha_worker.code_review_graph.extract_code_review_graph", lambda p, d: "graph_md")

    # Stub AGY calls:
    # Call 1 (Gemini 3.1 Pro): APPROVE
    # Call 2 (Claude Opus): Fails with RuntimeError (e.g. rate limit / network)
    # Call 3 (Claude Sonnet Fallback): FINAL_APPROVAL
    call_models = []

    def mock_invoke_agy(model, prompt, **kwargs):
        call_models.append(model)
        if model == "gemini-3.1-pro-high":
            return {"response": '{"verdict": "APPROVE"}', "structured_output": {"verdict": "APPROVE"}}
        if model == "claude-opus-4-6-thinking":
            raise RuntimeError("Claude Opus 503 Overloaded")
        if model == "claude-sonnet-4-6":
            return {"response": '{"verdict": "FINAL_APPROVAL"}', "structured_output": {"verdict": "FINAL_APPROVAL"}}
        return {"response": '{"verdict": "REJECT"}', "structured_output": {}}

    monkeypatch.setattr(engine, "_invoke_agy", mock_invoke_agy)
    monkeypatch.setenv("CLAUDE_ON_HOLIDAY", "0")
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "0")

    verdict = engine.execute_senior_review("tsk_test")

    assert verdict.approved is True
    assert "claude-opus-4-6-thinking" in call_models
    assert "claude-sonnet-4-6" in call_models
    assert verdict.round2_model == "claude-sonnet-4-6"
    assert verdict.degraded_same_family is False
    assert verdict.independence_status == INDEPENDENT_CROSS_PROVIDER
    assert verdict.founder_review_required is False


def test_senior_review_engine_degraded_same_family_fallback(monkeypatch, tmp_path):
    """
    Validates Invariant I-62:
    When both Opus and Sonnet fail, engine degrades to same-family gemini-3.1-pro-high,
    recording DEGRADED_SAME_FAMILY attestation trailer and requiring founder review.
    """
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": "completed",
        "branch_name": "alpha/tsk_test",
        "worktree_path": str(tmp_path),
        "provenance": {
            "lease_metadata": {"attempt_id": "att_1", "worker_id": "worker_1"}
        },
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "worker_1",
            "result_sha": "a" * 40,
        },
        "envelope": {"base_commit": "b" * 40},
    }

    engine = SeniorReviewEngine(
        queue=mock_queue,
        signing_secret="test_secret_key_value_32_bytes_len",
        key_id="alpha_production_v1",
    )

    monkeypatch.setattr(engine, "get_task_diff", lambda task: "diff --git a/f b/f")
    def mock_git(cmd, **kwargs):
        if "status" in cmd:
            return ""
        if "HEAD^{tree}" in cmd:
            return "c" * 40
        return "a" * 40

    monkeypatch.setattr("subprocess.check_output", mock_git)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stdout=""))
    monkeypatch.setattr("alpha_worker.code_review_graph.extract_code_review_graph", lambda p, d: "graph_md")

    call_models = []

    def mock_invoke_agy(model, prompt, **kwargs):
        call_models.append(model)
        if model == "gemini-3.1-pro-high":
            # For round 1 or round 2 degraded
            if len(call_models) == 1:
                return {"response": '{"verdict": "APPROVE"}', "structured_output": {"verdict": "APPROVE"}}
            else:
                return {"response": '{"verdict": "FINAL_APPROVAL"}', "structured_output": {"verdict": "FINAL_APPROVAL"}}
        if model in ("claude-opus-4-6-thinking", "claude-sonnet-4-6"):
            raise RuntimeError(f"{model} unavailable")
        return {"response": '{"verdict": "REJECT"}', "structured_output": {}}

    monkeypatch.setattr(engine, "_invoke_agy", mock_invoke_agy)
    monkeypatch.setenv("CLAUDE_ON_HOLIDAY", "0")
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "0")
    monkeypatch.setenv("BLOCK_ON_DEGRADED_SAME_FAMILY", "0")

    verdict = engine.execute_senior_review("tsk_test")

    assert "claude-opus-4-6-thinking" in call_models
    assert "claude-sonnet-4-6" in call_models
    assert verdict.round2_model == "gemini-3.1-pro-high"
    assert verdict.degraded_same_family is True
    assert verdict.independence_status == DEGRADED_SAME_FAMILY
    assert verdict.founder_review_required is True
    assert "[DEGRADED_SAME_FAMILY_ATTESTATION]" in verdict.opus_review_text
    assert verdict.attestation["degraded_same_family"] is True
    assert verdict.attestation["independence_status"] == DEGRADED_SAME_FAMILY


def test_senior_review_engine_degraded_same_family_blocking(monkeypatch, tmp_path):
    """
    Validates that when BLOCK_ON_DEGRADED_SAME_FAMILY=1, same-family degradation
    blocks auto-approval even if individual verdicts approved.
    """
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": "completed",
        "branch_name": "alpha/tsk_test",
        "worktree_path": str(tmp_path),
        "provenance": {
            "lease_metadata": {"attempt_id": "att_1", "worker_id": "worker_1"}
        },
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "worker_1",
            "result_sha": "a" * 40,
        },
        "envelope": {"base_commit": "b" * 40},
    }

    engine = SeniorReviewEngine(
        queue=mock_queue,
        signing_secret="test_secret_key_value_32_bytes_len",
        key_id="alpha_production_v1",
    )

    monkeypatch.setattr(engine, "get_task_diff", lambda task: "diff --git a/f b/f")
    def mock_git(cmd, **kwargs):
        if "status" in cmd:
            return ""
        if "HEAD^{tree}" in cmd:
            return "c" * 40
        return "a" * 40

    monkeypatch.setattr("subprocess.check_output", mock_git)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stdout=""))
    monkeypatch.setattr("alpha_worker.code_review_graph.extract_code_review_graph", lambda p, d: "graph_md")

    def mock_invoke_agy(model, prompt, **kwargs):
        return {"response": '{"verdict": "FINAL_APPROVAL"}', "structured_output": {"verdict": "FINAL_APPROVAL"}}

    monkeypatch.setattr(engine, "_invoke_agy", mock_invoke_agy)
    monkeypatch.setenv("CLAUDE_ON_HOLIDAY", "1")  # Trips holiday directly to gemini
    monkeypatch.setenv("ENABLE_CODEX_REVIEW", "0")
    monkeypatch.setenv("BLOCK_ON_DEGRADED_SAME_FAMILY", "1")

    verdict = engine.execute_senior_review("tsk_test")

    assert verdict.degraded_same_family is True
    assert verdict.approved is False  # Blocked!
    assert verdict.founder_review_required is True
