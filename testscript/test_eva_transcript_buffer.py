"""
testscript/test_eva_transcript_buffer.py
Unit tests verifying the debounced rolling transcript ring buffer for Eva.
"""

from alpha_core.eva.transcript_buffer import DebouncedTranscriptBuffer


def test_transcript_buffer_ingestion_and_formatting():
    buf = DebouncedTranscriptBuffer(debounce_seconds=30.0)

    buf.add_segment(
        "user_ajay", "Ajay (Founder)", "We need a Stripe checkout webhook.", timestamp=100.0
    )
    buf.add_segment(
        "user_client", "Client", "Yes, and it must verify signature headers.", timestamp=105.0
    )

    assert buf.total_segments == 2
    full = buf.get_full_formatted_transcript()
    assert "[Ajay (Founder)]: We need a Stripe checkout webhook." in full
    assert "[Client]: Yes, and it must verify signature headers." in full


def test_transcript_buffer_debounce_logic():
    buf = DebouncedTranscriptBuffer(debounce_seconds=30.0)

    # Ingest dialogue ending at t=100
    buf.add_segment("u1", "Ajay", "Let us build the analytics dashboard.", timestamp=100.0)

    # At t=110 (10s later), debounce period has NOT elapsed
    assert buf.is_extraction_due(current_time=110.0) is False

    # At t=129 (29s later), still not elapsed
    assert buf.is_extraction_due(current_time=129.0) is False

    # At t=130 (30s later), silence threshold reached!
    assert buf.is_extraction_due(current_time=130.0) is True


def test_transcript_buffer_watermark_and_deduplication():
    buf = DebouncedTranscriptBuffer(debounce_seconds=30.0)

    buf.add_segment("u1", "Ajay", "Task one requirements.", timestamp=10.0)
    buf.add_segment("u2", "Client", "Agreed on task one.", timestamp=20.0)

    unextracted = buf.get_unextracted_segments()
    assert len(unextracted) == 2

    # Mark extracted up to t=20.0
    buf.mark_extracted(up_to_timestamp=20.0)

    # Pending list should now be empty
    assert len(buf.get_unextracted_segments()) == 0
    assert buf.is_extraction_due(current_time=60.0) is False

    # Ingest new utterance at t=70.0
    buf.add_segment("u1", "Ajay", "Now moving to task two.", timestamp=70.0)
    new_unextracted = buf.get_unextracted_segments()
    assert len(new_unextracted) == 1
    assert new_unextracted[0].text == "Now moving to task two."


def test_transcript_buffer_continuous_window_fallback():
    # Test continuous discussion without 30s pause triggers extraction at max_continuous_window_seconds
    buf = DebouncedTranscriptBuffer(debounce_seconds=30.0, max_continuous_window_seconds=100.0)

    # Ingest continuous segments every 10 seconds from t=0 to t=90
    for t in range(0, 100, 10):
        buf.add_segment("u1", "Speaker", f"Speaking at {t}", timestamp=float(t))

    # At t=95, silence is only 5s (debounce 30s not met) and continuous duration is 95s < 100s
    assert buf.is_extraction_due(current_time=95.0) is False

    # At t=101, silence is only 11s, BUT continuous discussion has spanned 101s >= 100s!
    assert buf.is_extraction_due(current_time=101.0) is True
