import pytest

from app.policy.engine import CircuitBreaker, CircuitOpenError
from app.policy.rules import PolicyConfig

CFG = PolicyConfig(max_tool_calls_per_turn=3, max_consecutive_tool_errors=2)


def test_normal_usage_does_not_trip():
    cb = CircuitBreaker(CFG)
    for _ in range(3):
        cb.record_call()
        cb.record_result(is_error=False)
    assert cb.is_tripped is False


def test_exceeding_tool_calls_per_turn_trips():
    cb = CircuitBreaker(CFG)
    for _ in range(3):
        cb.record_call()
    with pytest.raises(CircuitOpenError):
        cb.record_call()
    assert cb.is_tripped is True
    assert "tool calls" in cb.tripped_reason


def test_consecutive_errors_trip_the_breaker():
    cb = CircuitBreaker(CFG)
    cb.record_call()
    cb.record_result(is_error=True)
    cb.record_call()
    with pytest.raises(CircuitOpenError):
        cb.record_result(is_error=True)
    assert "consecutive tool errors" in cb.tripped_reason


def test_a_success_resets_the_error_streak():
    cb = CircuitBreaker(CFG)
    cb.record_call()
    cb.record_result(is_error=True)
    cb.record_call()
    cb.record_result(is_error=False)
    cb.record_call()
    cb.record_result(is_error=True)
    assert cb.is_tripped is False


def test_reset_turn_clears_the_per_turn_call_budget():
    cb = CircuitBreaker(CFG)
    for _ in range(3):
        cb.record_call()
    cb.reset_turn()
    cb.record_call()
    assert cb.is_tripped is False
