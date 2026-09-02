import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.logger import log_action, new_correlation_id
from app.config import settings
from app.models import ApprovalRequest, Order, OrderItem, Product
from app.payments.razorpay_client import client as rzp
from app.policy.engine import evaluate_discount, evaluate_transaction
from app.policy.rules import PolicyConfig

log = logging.getLogger(__name__)

PAID_STATUSES = {"paid"}
SPENDING_STATUSES = {"paid", "pending_payment", "pending_approval"}


class PaymentError(Exception):
    """Carries a machine-readable code so the agent-facing tool layer can surface a
    structured error the model is prompted to handle, rather than a bare traceback."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _session_spend_to_date(db: Session, session_id: str) -> float:
    total = db.execute(
        select(func.coalesce(func.sum(Order.amount_inr), 0.0)).where(
            Order.session_id == session_id, Order.status.in_(SPENDING_STATUSES)
        )
    ).scalar_one()
    return float(total or 0.0)


def _is_first_time_buyer(db: Session, session_id: str) -> bool:
    count = db.execute(
        select(func.count(Order.id)).where(
            Order.session_id == session_id, Order.status.in_(PAID_STATUSES)
        )
    ).scalar_one()
    return int(count or 0) == 0


def _idempotency_key(session_id: str, items: list[dict], discount_pct: float) -> str:
    basis = f"{session_id}|{sorted((i['product_id'], i['qty']) for i in items)}|{discount_pct:g}"
    return hashlib.sha256(basis.encode()).hexdigest()[:48]


def _order_status_payload(order: Order) -> dict:
    return {
        "intent_id": order.id,
        "status": order.status,
        "amount_inr": order.amount_inr,
        "amount_paid_inr": order.amount_inr if order.status == "paid" else None,
        "failure_reason": order.failure_reason,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "razorpay_order_id": order.razorpay_order_id,
    }


def create_payment_intent(
    db: Session,
    *,
    session_id: str,
    items: list[dict],
    requested_discount_pct: float = 0.0,
    correlation_id: str | None = None,
    actor: str = "ai_buyer_agent",
) -> dict:
    cfg = PolicyConfig.from_settings()
    correlation_id = correlation_id or new_correlation_id()

    if not items:
        raise PaymentError("EMPTY_CART", "No items supplied.")
    if len(items) > cfg.max_items_per_order:
        raise PaymentError(
            "CART_LIMIT_EXCEEDED",
            f"{len(items)} line items exceeds the {cfg.max_items_per_order}-item policy limit.",
        )

    # Prices and stock are always re-derived from the DB — a tool caller can name products
    # and quantities, never prices.
    resolved: list[tuple[Product, int]] = []
    for item in items:
        product = db.get(Product, item["product_id"])
        if product is None:
            raise PaymentError("PRODUCT_NOT_FOUND", f"No product with id {item['product_id']}.")
        qty = max(1, int(item.get("qty", 1)))
        if product.stock_qty < qty:
            log_action(
                db,
                session_id=session_id,
                actor=actor,
                action_type="payment_failed",
                correlation_id=correlation_id,
                decision="blocked",
                explanation=(
                    f"{product.name} has {product.stock_qty} in stock but {qty} were requested; "
                    f"order not created."
                ),
                input_summary={"product_id": product.id, "requested_qty": qty},
                policy=cfg,
            )
            raise PaymentError(
                "INSUFFICIENT_STOCK",
                f"{product.name} only has {product.stock_qty} left (requested {qty}).",
            )
        resolved.append((product, qty))

    subtotal = sum(p.price_inr * q for p, q in resolved)

    discount = evaluate_discount(requested_discount_pct, cfg)
    total = round(subtotal * (1 - discount.capped_pct / 100), 2)

    if discount.was_capped:
        log_action(
            db,
            session_id=session_id,
            actor=actor,
            action_type="policy_decision",
            correlation_id=correlation_id,
            decision="capped",
            explanation=discount.explanation,
            input_summary={"requested_discount_pct": discount.requested_pct},
            output_summary={"applied_discount_pct": discount.capped_pct},
            policy=cfg,
        )

    txn = evaluate_transaction(
        total_inr=total,
        session_spend_to_date_inr=_session_spend_to_date(db, session_id),
        is_first_time_buyer=_is_first_time_buyer(db, session_id),
        cfg=cfg,
    )

    if txn.blocked:
        action = (
            "session_spend_cap_blocked" if "session cap" in txn.explanation else "policy_decision"
        )
        log_action(
            db,
            session_id=session_id,
            actor=actor,
            action_type=action,
            correlation_id=correlation_id,
            decision="blocked",
            explanation=txn.explanation,
            input_summary={"items": items, "requested_discount_pct": requested_discount_pct},
            amount_inr=total,
            policy=cfg,
        )
        code = (
            "SESSION_SPEND_CAP_EXCEEDED"
            if "session cap" in txn.explanation
            else "TXN_LIMIT_EXCEEDED"
        )
        raise PaymentError(code, txn.explanation)

    idem = _idempotency_key(session_id, items, discount.capped_pct)
    existing = db.execute(select(Order).where(Order.idempotency_key == idem)).scalar_one_or_none()
    if existing and existing.status not in {"failed", "expired"}:
        # Razorpay's Orders API has no idempotency header, so this is enforced app-side:
        # the same cart from the same session returns the same order instead of a duplicate.
        return _intent_payload(db, existing, txn, discount, cfg, reused=True)

    order = Order(
        session_id=session_id,
        idempotency_key=idem if not existing else f"{idem}:{new_correlation_id()[:8]}",
        amount_inr=total,
        discount_pct=discount.capped_pct,
        status="pending_approval" if txn.requires_approval else "created",
    )
    db.add(order)
    db.flush()
    for product, qty in resolved:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit_price_inr=product.price_inr,
                qty=qty,
            )
        )

    approval_id = None
    if txn.requires_approval:
        approval = ApprovalRequest(
            order_id=order.id,
            session_id=session_id,
            amount_inr=total,
            reason=txn.explanation,
        )
        db.add(approval)
        db.flush()
        approval_id = approval.id
        db.commit()
        log_action(
            db,
            session_id=session_id,
            actor=actor,
            action_type="approval_requested",
            correlation_id=correlation_id,
            decision="pending_approval",
            explanation=txn.explanation,
            input_summary={"items": items},
            amount_inr=total,
            order_id=order.id,
            policy=cfg,
        )
    else:
        _attach_razorpay_order(db, order, session_id)
        db.commit()
        log_action(
            db,
            session_id=session_id,
            actor=actor,
            action_type="create_payment_intent",
            correlation_id=correlation_id,
            decision="allowed",
            explanation=txn.explanation,
            input_summary={"items": items, "requested_discount_pct": requested_discount_pct},
            output_summary={"razorpay_order_id": order.razorpay_order_id},
            amount_inr=total,
            order_id=order.id,
            policy=cfg,
        )

    payload = _intent_payload(db, order, txn, discount, cfg)
    payload["approval_id"] = approval_id
    payload["correlation_id"] = correlation_id
    return payload


def _attach_razorpay_order(db: Session, order: Order, session_id: str) -> None:
    rzp_order = rzp.create_order(
        amount_paise=int(round(order.amount_inr * 100)),
        receipt=order.idempotency_key[:40],
        notes={"session_id": session_id, "internal_order_id": order.id},
    )
    order.razorpay_order_id = rzp_order["id"]
    order.status = "pending_payment"


def _intent_payload(
    db: Session,
    order: Order,
    txn,
    discount,
    cfg: PolicyConfig,
    reused: bool = False,
) -> dict:
    return {
        "intent_id": order.id,
        "razorpay_order_id": order.razorpay_order_id,
        "razorpay_key_id": settings.razorpay_key_id,
        "amount_inr": order.amount_inr,
        "currency": "INR",
        "status": order.status,
        "reused_existing_order": reused,
        "policy_decision": {
            "requested_discount_pct": discount.requested_pct,
            "capped_discount_pct": discount.capped_pct,
            "was_capped": discount.was_capped,
            "requires_approval": txn.requires_approval,
            "explanation": (
                discount.explanation + " " + txn.explanation
                if discount.was_capped
                else txn.explanation
            ),
        },
    }


def get_order_status(db: Session, intent_id: str) -> dict:
    order = db.get(Order, intent_id)
    if order is None:
        raise PaymentError("ORDER_NOT_FOUND", f"No order with id {intent_id}.")
    return _order_status_payload(order)


def approve_order(db: Session, approval_id: str, approve: bool) -> dict:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise PaymentError("APPROVAL_NOT_FOUND", f"No approval request with id {approval_id}.")
    if approval.status != "pending":
        raise PaymentError("APPROVAL_ALREADY_DECIDED", f"Already {approval.status}.")

    order = db.get(Order, approval.order_id)
    approval.status = "approved" if approve else "denied"
    approval.decided_at = datetime.now(timezone.utc)

    if approve:
        _attach_razorpay_order(db, order, approval.session_id)
        explanation = (
            f"Merchant approved ₹{order.amount_inr:g} order; Razorpay order created and "
            f"handed back for payment."
        )
    else:
        order.status = "failed"
        order.failure_reason = "Merchant denied the order at the approval gate."
        explanation = f"Merchant denied the ₹{order.amount_inr:g} order at the approval gate."

    db.commit()
    log_action(
        db,
        session_id=approval.session_id,
        actor="merchant_human",
        action_type="approval_decided",
        correlation_id=new_correlation_id(),
        decision="approved" if approve else "denied",
        explanation=explanation,
        amount_inr=order.amount_inr,
        order_id=order.id,
        policy=PolicyConfig.from_settings(),
    )
    return _order_status_payload(order)


def mark_paid(
    db: Session,
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    source: str,
) -> Order | None:
    """Idempotent terminal transition, shared by the client-side verify callback and the
    webhook — whichever arrives first wins, the second is a no-op."""
    order = db.execute(
        select(Order).where(Order.razorpay_order_id == razorpay_order_id)
    ).scalar_one_or_none()
    if order is None:
        return None
    if order.status == "paid":
        return order

    order.status = "paid"
    order.razorpay_payment_id = razorpay_payment_id
    order.paid_at = datetime.now(timezone.utc)

    for item in order.items:
        product = db.get(Product, item.product_id)
        if product is not None:
            product.stock_qty = max(0, product.stock_qty - item.qty)

    db.commit()
    log_action(
        db,
        session_id=order.session_id,
        actor="system",
        action_type="payment_confirmed",
        correlation_id=new_correlation_id(),
        decision="allowed",
        explanation=f"Payment confirmed via {source} for ₹{order.amount_inr:g}.",
        output_summary={"razorpay_payment_id": razorpay_payment_id, "source": source},
        amount_inr=order.amount_inr,
        order_id=order.id,
        policy=PolicyConfig.from_settings(),
    )
    return order


def mark_failed(db: Session, *, razorpay_order_id: str, reason: str, source: str) -> Order | None:
    order = db.execute(
        select(Order).where(Order.razorpay_order_id == razorpay_order_id)
    ).scalar_one_or_none()
    if order is None or order.status == "paid":
        return order

    order.status = "failed"
    order.failure_reason = reason
    db.commit()
    log_action(
        db,
        session_id=order.session_id,
        actor="system",
        action_type="payment_failed",
        correlation_id=new_correlation_id(),
        decision="blocked",
        explanation=f"Payment failed ({source}): {reason}",
        amount_inr=order.amount_inr,
        order_id=order.id,
        policy=PolicyConfig.from_settings(),
    )
    return order
