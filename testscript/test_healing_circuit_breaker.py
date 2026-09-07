import time

from alpha_core.healing.circuit_breaker import CircuitBreaker, CircuitBreakerState, TripReason


def test_circuit_breaker_initial_state():
    cb = CircuitBreaker()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.attempts == 0
    assert cb.get_backoff_delay() == 0.0
    assert cb.can_attempt() is True

def test_circuit_breaker_exponential_backoff():
    cb = CircuitBreaker(base_delay_sec=1.0)

    cb.record_failure("sig1")
    assert cb.attempts == 1
    assert cb.get_backoff_delay() == 1.0

    cb.record_failure("sig2")
    assert cb.attempts == 2
    assert cb.get_backoff_delay() == 2.0

    cb.record_failure("sig3")
    assert cb.attempts == 3
    assert cb.get_backoff_delay() == 4.0

def test_circuit_breaker_trips_on_identical_signatures():
    # Invariant I-38
    cb = CircuitBreaker(max_identical_signatures=3)

    reason1 = cb.record_failure("sig_A")
    assert reason1 == TripReason.NONE
    assert cb.state == CircuitBreakerState.CLOSED

    reason2 = cb.record_failure("sig_A")
    assert reason2 == TripReason.NONE
    assert cb.state == CircuitBreakerState.CLOSED

    # 3rd identical failure should trip the breaker
    reason3 = cb.record_failure("sig_A")
    assert reason3 == TripReason.ESCALATED_HUMAN_REVIEW
    assert cb.state == CircuitBreakerState.OPEN

def test_circuit_breaker_half_open_transition():
    cb = CircuitBreaker(max_attempts=3, reset_timeout_sec=60.0)

    # Trip it
    cb.record_failure("sig1")
    cb.record_failure("sig2")
    cb.record_failure("sig3")

    assert cb.state == CircuitBreakerState.OPEN

    # Time hasn't passed, should still be OPEN
    assert not cb.can_attempt(current_time=time.time())

    # Simulate time passing
    future_time = time.time() + 61.0
    assert cb.can_attempt(current_time=future_time)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Failure in HALF_OPEN trips immediately
    reason = cb.record_failure("sig4", current_time=future_time)
    assert reason == TripReason.ESCALATED_HUMAN_REVIEW
    assert cb.state == CircuitBreakerState.OPEN

def test_circuit_breaker_record_success():
    cb = CircuitBreaker()
    cb.record_failure("sig1")
    cb.record_failure("sig2")

    assert cb.attempts == 2
    assert cb.state == CircuitBreakerState.CLOSED

    cb.record_success()
    assert cb.attempts == 0
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.get_backoff_delay() == 0.0
