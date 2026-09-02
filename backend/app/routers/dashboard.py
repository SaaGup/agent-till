from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.llm import llm_enabled
from app.auth.service import require_merchant
from app.config import settings
from app.db import get_db
from app.models import ApprovalRequest, AuditLogEntry, Order, Product, User
from app.payments.service import PaymentError, approve_order

router = APIRouter(prefix="/api", tags=["dashboard"])


class ApprovalDecision(BaseModel):
    approve: bool


@router.get("/config")
def public_config() -> dict:
    """Only ever the publishable key id — the secret stays server-side."""
    return {
        "razorpay_key_id": settings.razorpay_key_id,
        "payments_live": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
        "agent_enabled": llm_enabled(),
        # Deliberately published: this is a public demo and judges need a way in. A real
        # deployment sets its own merchant credentials via env and would drop these.
        "demo_merchant_email": settings.demo_merchant_email,
        "demo_merchant_password": settings.demo_merchant_password,
    }


@router.get("/catalog")
def list_catalog(db: Session = Depends(get_db)) -> list[dict]:
    products = db.execute(select(Product).order_by(Product.category, Product.price_inr)).scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price_inr": p.price_inr,
            "category": p.category,
            "stock_qty": p.stock_qty,
            "tags": p.tags,
        }
        for p in products
    ]


@router.get("/orders")
def list_orders(db: Session = Depends(get_db), limit: int = 25) -> list[dict]:
    orders = db.execute(select(Order).order_by(desc(Order.created_at)).limit(limit)).scalars().all()
    return [
        {
            "id": o.id,
            "session_id": o.session_id,
            "amount_inr": o.amount_inr,
            "discount_pct": o.discount_pct,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "items": [
                {"name": i.product_name, "qty": i.qty, "unit_price_inr": i.unit_price_inr}
                for i in o.items
            ],
        }
        for o in orders
    ]


@router.get("/audit-log")
def list_audit_log(db: Session = Depends(get_db), limit: int = 100) -> list[dict]:
    rows = db.execute(select(AuditLogEntry).order_by(desc(AuditLogEntry.ts)).limit(limit)).scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat() if r.ts else None,
            "correlation_id": r.correlation_id,
            "session_id": r.session_id,
            "actor": r.actor,
            "action_type": r.action_type,
            "money_affecting": r.money_affecting,
            "decision": r.decision,
            "explanation": r.explanation,
            "amount_inr": r.amount_inr,
            "order_id": r.order_id,
            "policy_snapshot": r.policy_snapshot,
        }
        for r in rows
    ]


@router.get("/approvals")
def list_approvals(
    db: Session = Depends(get_db), _: User = Depends(require_merchant)
) -> list[dict]:
    rows = (
        db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .order_by(desc(ApprovalRequest.created_at))
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": a.id,
            "order_id": a.order_id,
            "session_id": a.session_id,
            "amount_inr": a.amount_inr,
            "reason": a.reason,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


@router.post("/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    _: User = Depends(require_merchant),
) -> dict:
    try:
        return approve_order(db, approval_id, body.approve)
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict:
    orders = db.execute(select(Order)).scalars().all()
    paid = [o for o in orders if o.status == "paid"]
    return {
        "orders_total": len(orders),
        "orders_paid": len(paid),
        "revenue_inr": round(sum(o.amount_inr for o in paid), 2),
        "pending_approvals": len([o for o in orders if o.status == "pending_approval"]),
        "audit_entries": db.query(AuditLogEntry).count(),
    }


@router.post("/demo/force-out-of-stock/{product_id}")
def force_out_of_stock(
    product_id: str,
    x_demo_key: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    # Deliberately breaks catalog state for the failure demo, so it must not be publicly
    # triggerable on a live URL.
    if not settings.demo_key or x_demo_key != settings.demo_key:
        raise HTTPException(status_code=403, detail="Invalid demo key.")
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Unknown product.")
    previous = product.stock_qty
    product.stock_qty = 0
    db.commit()
    return {"product_id": product_id, "previous_stock": previous, "stock_qty": 0}


@router.post("/demo/restock/{product_id}")
def restock(
    product_id: str, qty: int = 10, x_demo_key: str = Header(default=""), db: Session = Depends(get_db)
) -> dict:
    if not settings.demo_key or x_demo_key != settings.demo_key:
        raise HTTPException(status_code=403, detail="Invalid demo key.")
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Unknown product.")
    product.stock_qty = qty
    db.commit()
    return {"product_id": product_id, "stock_qty": qty}
