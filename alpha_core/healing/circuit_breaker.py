import enum
import time
from typing import Any


class CircuitBreakerState(enum.Enum):
    CLOSED = "CLOSED"
    HALF_OPEN = "HALF_OPEN"
    OPEN = "OPEN"


class TripReason(enum.Enum):
    NONE = "NONE"
    ESCALATED_HUMAN_REVIEW = "ESCALATED_HUMAN_REVIEW"


class CircuitBreaker:
    """
    Implements a circuit breaker for repair attempts, enforcing Invariant I-38:
    Trip to ESCALATED_HUMAN_REVIEW on repeated identical failure signatures to prevent thrashing.
    Manages CLOSED, HALF_OPEN, and OPEN states, and computes exponential backoff delays.
    """

    def __init__(
        self,
        max_identical_signatures: int = 3,
        max_attempts: int = 5,
        base_delay_sec: float = 1.0,
        reset_timeout_sec: float = 60.0,
    ):
        self.state = CircuitBreakerState.CLOSED
        self.max_identical_signatures = max_identical_signatures
        self.max_attempts = max_attempts
        self.base_delay_sec = base_delay_sec
        self.reset_timeout_sec = reset_timeout_sec

        self.attempts = 0
        self.identical_count = 0
        self.last_signature: str | None = None
        self.opened_at = 0.0
        self.trip_reason = TripReason.NONE

    def _update_state(self, current_time: float):
        if self.state == CircuitBreakerState.OPEN:
            if current_time - self.opened_at >= self.reset_timeout_sec:
                self.state = CircuitBreakerState.HALF_OPEN

    def record_failure(self, signature: str, current_time: float | None = None) -> TripReason:
        if current_time is None:
            current_time = time.time()

        self._update_state(current_time)

        if self.state == CircuitBreakerState.OPEN:
            return TripReason.ESCALATED_HUMAN_REVIEW

        if self.state == CircuitBreakerState.HALF_OPEN:
            # A failure in HALF_OPEN trips immediately back to OPEN
            self.state = CircuitBreakerState.OPEN
            self.opened_at = current_time
            self.trip_reason = TripReason.ESCALATED_HUMAN_REVIEW
            return self.trip_reason

        # State is CLOSED
        self.attempts += 1

        if self.last_signature == signature:
            self.identical_count += 1
        else:
            self.last_signature = signature
            self.identical_count = 1

        # Invariant I-38: Trip to ESCALATED_HUMAN_REVIEW on repeated identical failures
        if (
            self.identical_count >= self.max_identical_signatures
            or self.attempts >= self.max_attempts
        ):
            self.state = CircuitBreakerState.OPEN
            self.opened_at = current_time
            self.trip_reason = TripReason.ESCALATED_HUMAN_REVIEW
            return self.trip_reason

        return TripReason.NONE

    def record_success(self):
        """
        Resets the circuit breaker on a successful repair.
        """
        self.state = CircuitBreakerState.CLOSED
        self.attempts = 0
        self.identical_count = 0
        self.last_signature = None
        self.trip_reason = TripReason.NONE

    def get_backoff_delay(self) -> float:
        """
        Computes exponential backoff delay based on the number of attempts.
        Returns 0.0 if no attempts have been made.
        """
        if self.attempts == 0:
            return 0.0
        return self.base_delay_sec * (2.0 ** (self.attempts - 1))

    def can_attempt(self, current_time: float | None = None) -> bool:
        """
        Checks if a repair attempt is allowed in the current state.
        """
        if current_time is None:
            current_time = time.time()
        self._update_state(current_time)
        return self.state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)

    def to_dict(self) -> dict[str, object]:
        """Serializes the circuit breaker state to a dictionary for persistence."""
        return {
            "state": self.state.value,
            "max_identical_signatures": self.max_identical_signatures,
            "max_attempts": self.max_attempts,
            "base_delay_sec": self.base_delay_sec,
            "reset_timeout_sec": self.reset_timeout_sec,
            "attempts": self.attempts,
            "identical_count": self.identical_count,
            "last_signature": self.last_signature,
            "opened_at": self.opened_at,
            "trip_reason": self.trip_reason.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CircuitBreaker":
        """Reconstructs a CircuitBreaker from a serialized dictionary."""
        cb = cls(
            max_identical_signatures=int(data.get("max_identical_signatures", 3)),
            max_attempts=int(data.get("max_attempts", 5)),
            base_delay_sec=float(data.get("base_delay_sec", 1.0)),
            reset_timeout_sec=float(data.get("reset_timeout_sec", 60.0)),
        )
        state_str = str(data.get("state", CircuitBreakerState.CLOSED.value))
        cb.state = CircuitBreakerState(state_str)
        cb.attempts = int(data.get("attempts", 0))
        cb.identical_count = int(data.get("identical_count", 0))
        raw_sig = data.get("last_signature")
        cb.last_signature = str(raw_sig) if raw_sig is not None else None
        cb.opened_at = float(data.get("opened_at", 0.0))
        reason_str = str(data.get("trip_reason", TripReason.NONE.value))
        cb.trip_reason = TripReason(reason_str)
        return cb

    @staticmethod
    def execute_transactionally(queue, root_id: str, action_fn):
        # Note: fcntl is a POSIX-only module (Linux/macOS).
        # We use a single global lock file to prevent filesystem inode bloat.
        import fcntl
        lock_file = str(queue.db_path) + ".cb.lock"
        with open(lock_file, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                state_dict = queue.get_circuit_breaker(root_id)
                if state_dict:
                    cb = CircuitBreaker.from_dict(state_dict)
                else:
                    cb = CircuitBreaker()

                result = action_fn(cb)

                queue.save_circuit_breaker(root_id, cb.to_dict())
                return result, cb
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
