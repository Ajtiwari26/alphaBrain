from alpha_core.commentary import LiveCommentaryEngine


def test_translate_state_change():
    engine = LiveCommentaryEngine()

    # Test known state
    msg = engine.translate_state_change("T-123", "queued", "executing")
    assert msg == "Task T-123 is now actively writing code and applying changes."

    # Test unknown state (should fall back to raw string with spaces)
    msg = engine.translate_state_change("T-124", "executing", "custom_state")
    assert msg == "Task T-124 is now custom state."

def test_translate_gate_check():
    engine = LiveCommentaryEngine()

    # Test pass
    msg = engine.translate_gate_check("unit_test", True)
    assert msg == "Passed the Unit Test quality check."

    # Test fail without error
    msg = engine.translate_gate_check("lint", False)
    assert msg == "Did not pass the Lint quality check."

    # Test fail with error
    msg = engine.translate_gate_check("security", False, "high severity vulnerability found")
    assert msg == "Did not pass the Security quality check due to an issue: high severity vulnerability found"

def test_translate_review_debate():
    engine = LiveCommentaryEngine()

    # Test approve
    msg = engine.translate_review_debate("Claude Opus", "approve", "Looks good to me.")
    assert msg == "Claude Opus approved the changes. Note: Looks good to me."

    # Test reject
    msg = engine.translate_review_debate("Gemini Pro", "repair", "Missing edge cases in tests.")
    assert msg == "Gemini Pro requested revisions. Feedback: Missing edge cases in tests."

    # Test other
    msg = engine.translate_review_debate("Human Reviewer", "defer", "Let's look at this later.")
    assert msg == "Human Reviewer provided a review verdict of 'defer'. Note: Let's look at this later."

def test_translate_event_dispatcher():
    engine = LiveCommentaryEngine()

    msg = engine.translate_event("state_change", {"task_id": "T-1", "to_state": "completed"})
    assert msg == "Task T-1 is now successfully finished and ready."

    msg = engine.translate_event("gate_check", {"gate_name": "lint", "passed": True})
    assert msg == "Passed the Lint quality check."

    msg = engine.translate_event("review_debate", {"reviewer": "Alice", "verdict": "pass", "comments": "LGTM"})
    assert msg == "Alice approved the changes. Note: LGTM"

    msg = engine.translate_event("unknown_event", {})
    assert msg == "System event occurred: unknown event."
