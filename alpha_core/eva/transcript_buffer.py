"""
alpha_core/eva/transcript_buffer.py
Rolling ring buffer and debounced aggregator for live meeting speech transcripts.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 4.2)
"""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranscriptSegment:
    """Represents an atomic speech utterance from a meeting participant."""

    speaker_id: str
    speaker_name: str
    text: str
    timestamp: float = field(default_factory=time.time)
    is_final: bool = True

    def format_line(self) -> str:
        return f"[{self.speaker_name}]: {self.text.strip()}"


class DebouncedTranscriptBuffer:
    """Maintains a sliding window of meeting dialogue with debounced extraction triggers.

    Invariants:
    - Minimum debounced silence window (default 30.0 seconds).
    - Preserves ordering of utterances.
    - Tracks highest consumed timestamp to prevent duplicate task proposals.
    """

    def __init__(
        self,
        debounce_seconds: float = 30.0,
        max_history_segments: int = 1000,
    ) -> None:
        self.debounce_seconds = debounce_seconds
        self.max_history_segments = max_history_segments
        self._history: deque[TranscriptSegment] = deque(maxlen=max_history_segments)
        self._last_speech_time: float = 0.0
        self._last_extracted_timestamp: float = 0.0

    def add_segment(
        self,
        speaker_id: str,
        speaker_name: str,
        text: str,
        timestamp: float | None = None,
        is_final: bool = True,
    ) -> TranscriptSegment:
        """Appends a new utterance to the buffer and updates the speech activity timer."""
        cleaned_text = text.strip()
        if not cleaned_text:
            return TranscriptSegment(speaker_id=speaker_id, speaker_name=speaker_name, text="")

        ts = timestamp if timestamp is not None else time.time()
        seg = TranscriptSegment(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            text=cleaned_text,
            timestamp=ts,
            is_final=is_final,
        )
        self._history.append(seg)
        self._last_speech_time = ts
        return seg

    def is_extraction_due(self, current_time: float | None = None) -> bool:
        """Returns True if there is unextracted speech and the debounce silence period has elapsed."""
        now = current_time if current_time is not None else time.time()
        unextracted = self.get_unextracted_segments()
        if not unextracted:
            return False

        # If enough silence has passed since the last utterance
        silence_duration = now - self._last_speech_time
        return silence_duration >= self.debounce_seconds

    def get_unextracted_segments(self) -> list[TranscriptSegment]:
        """Returns all speech segments recorded after the last successful extraction timestamp."""
        return [
            seg
            for seg in self._history
            if seg.timestamp > self._last_extracted_timestamp and seg.text
        ]

    def get_full_formatted_transcript(self) -> str:
        """Returns the entire session dialogue formatted chronologically."""
        return "\n".join(seg.format_line() for seg in self._history if seg.text)

    def get_unextracted_formatted_transcript(self) -> str:
        """Returns only the pending, unextracted dialogue formatted chronologically."""
        unextracted = self.get_unextracted_segments()
        return "\n".join(seg.format_line() for seg in unextracted)

    def mark_extracted(self, up_to_timestamp: float | None = None) -> None:
        """Advances the extraction watermark to prevent duplicate task generation."""
        if up_to_timestamp is not None:
            self._last_extracted_timestamp = max(self._last_extracted_timestamp, up_to_timestamp)
        elif self._history:
            self._last_extracted_timestamp = max(
                self._last_extracted_timestamp, self._history[-1].timestamp
            )

    def clear(self) -> None:
        """Resets the buffer."""
        self._history.clear()
        self._last_speech_time = 0.0
        self._last_extracted_timestamp = 0.0

    @property
    def total_segments(self) -> int:
        return len(self._history)
