"""
testscript/test_eva_spec_extractor.py
Unit tests verifying the structured specification extractor for Eva.
"""

from unittest.mock import MagicMock

from alpha_core.eva.spec_extractor import EvaSpecificationExtractor


def test_spec_extractor_empty_transcript():
    extractor = EvaSpecificationExtractor(api_key="mock_key")
    assert extractor.extract_from_transcript("") is None
    assert extractor.extract_from_transcript("   ") is None


def test_spec_extractor_actionable_feature():
    extractor = EvaSpecificationExtractor(api_key="mock_key")

    mock_json = """
    {
      "is_actionable": true,
      "confidence_score": 0.95,
      "title": "Stripe Webhook Signature Verification",
      "summary": "Implement HMAC SHA256 signature verification for Stripe webhooks.",
      "requirements": ["Verify Stripe-Signature header", "Reject replayed timestamps > 300s"],
      "acceptance_criteria": ["Return 400 for invalid signature", "Return 200 for valid event"],
      "allowed_paths": ["alpha_core/api/webhooks.py", "testscript/test_webhooks.py"],
      "required_gates": ["unit_test", "lint"]
    }
    """

    mock_response = MagicMock()
    mock_response.text = mock_json
    extractor.client = MagicMock()
    extractor.client.models.generate_content.return_value = mock_response

    transcript = "[Ajay]: Eva, we need Stripe webhook signature verification on the API."
    spec = extractor.extract_from_transcript(transcript)

    assert spec is not None
    assert spec.is_actionable is True
    assert spec.confidence_score == 0.95
    assert spec.title == "Stripe Webhook Signature Verification"
    assert "Verify Stripe-Signature header" in spec.requirements
    assert "alpha_core/api/webhooks.py" in spec.allowed_paths


def test_spec_extractor_casual_chat_non_actionable():
    extractor = EvaSpecificationExtractor(api_key="mock_key")

    mock_json = """
    {
      "is_actionable": false,
      "confidence_score": 0.1,
      "title": "Greeting",
      "summary": "Participants saying hello",
      "requirements": [],
      "acceptance_criteria": [],
      "allowed_paths": []
    }
    """

    mock_response = MagicMock()
    mock_response.text = mock_json
    extractor.client = MagicMock()
    extractor.client.models.generate_content.return_value = mock_response

    transcript = "[Ajay]: Good morning. [Client]: Hello, how are you today?"
    spec = extractor.extract_from_transcript(transcript)

    assert spec is not None
    assert spec.is_actionable is False
    assert spec.confidence_score < 0.6
