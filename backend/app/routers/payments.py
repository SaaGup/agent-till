from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.rate_limit import PAYMENT_LIMIT, limiter
from app.payments.razorpay_client import client as rzp
from app.payments.service import mark_failed, mark_paid

router = APIRouter(prefix="/api/payments", tags=["payments"])


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class FailedRequest(BaseModel):
    razorpay_order_id: str
    reason: str = "Payment failed at the gateway."


@router.post("/verify")
@limiter.limit(PAYMENT_LIMIT)
def verify_payment(request: Request, body: VerifyRequest, db: Session = Depends(get_db)) -> dict:
    """Client-side confirmation path. The webhook is the trustworthy source of truth, but a
    signature-verified callback lets the UI update immediately instead of polling."""
    if not rzp.verify_payment_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Invalid payment signature.")

    order = mark_paid(
        db,
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        source="checkout_callback",
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Unknown order.")
    return {"status": order.status, "intent_id": order.id, "amount_inr": order.amount_inr}


@router.post("/failed")
@limiter.limit(PAYMENT_LIMIT)
def report_failed(request: Request, body: FailedRequest, db: Session = Depends(get_db)) -> dict:
    order = mark_failed(
        db, razorpay_order_id=body.razorpay_order_id, reason=body.reason, source="checkout_callback"
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Unknown order.")
    return {"status": order.status, "intent_id": order.id}
