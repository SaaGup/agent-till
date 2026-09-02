"""The session id must stay out of the model's reach.

It was briefly a tool parameter, and the agent invented its own value rather than passing the
real one. Because the cumulative spend cap and the first-time-buyer gate both key off the
session id, a model that picks it gets a fresh ₹0 budget per order and the cap stops meaning
anything. These tests pin the fix.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.catalog.data import seed_catalog
from app.models import Base
from app.payments.service import PaymentError, create_payment_intent
from app.policy.rules import PolicyConfig


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_catalog(session)
    yield session
    session.close()


def test_session_id_is_not_a_tool_parameter():
    """If this fails, the model can name the session it spends from."""
    import inspect

    from mcp_server.server import create_payment_intent_tool

    params = set(inspect.signature(create_payment_intent_tool).parameters)
    assert "buyer_session_id" not in params
    assert "session_id" not in params
    assert params == {"items", "requested_discount_pct"}


# Distinct carts, because an identical cart is deliberately deduplicated by the idempotency key
# and would return the existing order rather than adding to session spend.
_CART_SEQUENCE = ["shoe-trail-2499", "shoe-velocity-2999", "jacket-shell-3299"]


def test_spend_cap_accumulates_within_one_session(db):
    cfg = PolicyConfig.from_settings()
    assert cfg.max_session_spend_inr == 8000.0

    # ₹2,499 + ₹2,999 = ₹5,498, still under the cap.
    for product_id in _CART_SEQUENCE[:2]:
        create_payment_intent(db, session_id="capped", items=[{"product_id": product_id, "qty": 1}])

    # + ₹3,299 = ₹8,797, over it.
    with pytest.raises(PaymentError) as exc:
        create_payment_intent(
            db, session_id="capped", items=[{"product_id": _CART_SEQUENCE[2], "qty": 1}]
        )
    assert exc.value.code == "SESSION_SPEND_CAP_EXCEEDED"


def test_a_different_session_gets_its_own_budget(db):
    """The cap is per-session — which is exactly why the id must not be model-chosen."""
    for product_id in _CART_SEQUENCE[:2]:
        create_payment_intent(db, session_id="session-a", items=[{"product_id": product_id, "qty": 1}])
    with pytest.raises(PaymentError):
        create_payment_intent(
            db, session_id="session-a", items=[{"product_id": _CART_SEQUENCE[2], "qty": 1}]
        )

    fresh = create_payment_intent(
        db, session_id="session-b", items=[{"product_id": _CART_SEQUENCE[2], "qty": 1}]
    )
    assert fresh["status"] in {"created", "pending_approval", "pending_payment"}


def test_identical_cart_is_deduplicated_rather_than_double_charged(db):
    first = create_payment_intent(
        db, session_id="dedupe", items=[{"product_id": "shoe-trail-2499", "qty": 1}]
    )
    second = create_payment_intent(
        db, session_id="dedupe", items=[{"product_id": "shoe-trail-2499", "qty": 1}]
    )
    assert second["intent_id"] == first["intent_id"]
    assert second["reused_existing_order"] is True
