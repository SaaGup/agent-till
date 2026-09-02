import pytest

from app.policy.engine import evaluate_discount, evaluate_transaction
from app.policy.rules import PolicyConfig

CFG = PolicyConfig(
    max_discount_pct=20.0,
    approval_threshold_inr=3000.0,
    max_txn_value_inr=5000.0,
    max_session_spend_inr=8000.0,
)


def test_discount_within_cap_is_untouched():
    d = evaluate_discount(15.0, CFG)
    assert d.capped_pct == 15.0
    assert d.was_capped is False
    assert "within" in d.explanation


def test_discount_over_cap_is_clamped():
    d = evaluate_discount(35.0, CFG)
    assert d.capped_pct == 20.0
    assert d.was_capped is True
    assert "capped to 20%" in d.explanation


def test_discount_exactly_at_cap_is_not_flagged_as_capped():
    d = evaluate_discount(20.0, CFG)
    assert d.capped_pct == 20.0
    assert d.was_capped is False


def test_negative_discount_is_floored_at_zero():
    d = evaluate_discount(-10.0, CFG)
    assert d.capped_pct == 0.0
    assert d.was_capped is False


def test_small_repeat_order_is_allowed_without_approval():
    t = evaluate_transaction(1500.0, session_spend_to_date_inr=500.0, is_first_time_buyer=False, cfg=CFG)
    assert t.decision == "allowed"
    assert t.requires_approval is False
    assert t.blocked is False


def test_first_time_buyer_always_requires_approval():
    t = evaluate_transaction(500.0, session_spend_to_date_inr=0.0, is_first_time_buyer=True, cfg=CFG)
    assert t.decision == "pending_approval"
    assert t.requires_approval is True
    assert "first transaction" in t.explanation


def test_over_approval_threshold_requires_approval():
    t = evaluate_transaction(3500.0, session_spend_to_date_inr=0.0, is_first_time_buyer=False, cfg=CFG)
    assert t.decision == "pending_approval"
    assert "approval threshold" in t.explanation


def test_over_per_transaction_hard_cap_is_blocked_not_gated():
    t = evaluate_transaction(5999.0, session_spend_to_date_inr=0.0, is_first_time_buyer=False, cfg=CFG)
    assert t.decision == "blocked"
    assert t.blocked is True
    assert t.requires_approval is False
    assert t.allowed is False


def test_session_spend_cap_blocks_even_when_single_order_is_fine():
    t = evaluate_transaction(2000.0, session_spend_to_date_inr=7000.0, is_first_time_buyer=False, cfg=CFG)
    assert t.decision == "blocked"
    assert "session cap" in t.explanation


def test_order_exactly_at_thresholds_is_not_over_them():
    t = evaluate_transaction(3000.0, session_spend_to_date_inr=0.0, is_first_time_buyer=False, cfg=CFG)
    assert t.decision == "allowed"


def test_every_decision_carries_a_non_empty_explanation():
    cases = [
        (1000.0, 0.0, False),
        (1000.0, 0.0, True),
        (3500.0, 0.0, False),
        (9000.0, 0.0, False),
        (2000.0, 7500.0, False),
    ]
    for total, spent, first_time in cases:
        t = evaluate_transaction(total, spent, first_time, CFG)
        assert t.explanation.strip(), f"missing explanation for {total=} {spent=} {first_time=}"


@pytest.mark.parametrize("requested", [0.0, 5.0, 19.9, 20.0, 20.1, 100.0])
def test_discount_never_exceeds_cap_for_any_request(requested):
    assert evaluate_discount(requested, CFG).capped_pct <= CFG.max_discount_pct
