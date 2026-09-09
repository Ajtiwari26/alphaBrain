"""
Tests for SP2 Research Broker SSRF/redirect bounds and caching.
"""

import pytest
from pathlib import Path

from alpha_core.planning.research_broker import ResearchBroker, SSRFViolationError

def test_research_broker_ssrf_protection():
    broker = ResearchBroker()

    # Localhost should be blocked
    with pytest.raises(SSRFViolationError):
        broker.fetch_url("http://127.0.0.1:8080/secret")
        
    with pytest.raises(SSRFViolationError):
        broker.fetch_url("http://localhost:5000/api")

    # Internal IPs should be blocked
    with pytest.raises(SSRFViolationError):
        broker.fetch_url("http://192.168.1.1/admin")

    with pytest.raises(SSRFViolationError):
        broker.fetch_url("http://10.0.0.1/dashboard")

    # Non-http schemes should be blocked
    with pytest.raises(SSRFViolationError):
        broker.fetch_url("file:///etc/passwd")

def test_research_broker_capability_detection():
    broker = ResearchBroker()
    caps = broker.detect_capabilities()
    assert caps["web_search_available"] is True
    assert caps["code_review_graph_available"] is True

def test_graph_freshness_mock(monkeypatch):
    broker = ResearchBroker()

    def mock_run(*args, **kwargs):
        class MockRes:
            stdout = "abcd1234abcd1234abcd1234abcd1234abcd1234\n"
        return MockRes()

    monkeypatch.setattr("subprocess.run", mock_run)

    assert broker.check_graph_freshness(Path("/fake"), "abcd1234abcd1234abcd1234abcd1234abcd1234") is True
    assert broker.check_graph_freshness(Path("/fake"), "wrongsha") is False
