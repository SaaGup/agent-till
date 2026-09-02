import logging

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.payments.razorpay_client import client as rzp
from app.payments.service import mark_failed, mark_paid

log = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    db: Session = Depends(get_db),
) -> JSONResponse:
    raw = await request.body()

    # Signature is verified over the RAW bytes — parsing first and re-serializing would
    # change the payload and break the HMAC. This endpoint is public, so an unverified
    # body is never allowed to move an order to paid.
    if not rzp.verify_webhook_signature(raw, x_razorpay_signature):
        log.warning("rejected webhook with invalid signature")
        return JSONResponse(status_code=400, content={"error": "invalid_signature"})

    payload = await request.json()
    event = payload.get("event", "")
    entity = (
        payload.get("payload", {}).get("payment", {}).get("entity", {})
        or payload.get("payload", {}).get("order", {}).get("entity", {})
    )
    order_id = entity.get("order_id") or entity.get("id")

    if not order_id:
        return JSONResponse(content={"status": "ignored", "reason": "no order id in payload"})

    if event in {"payment.captured", "order.paid"}:
        mark_paid(
            db,
            razorpay_order_id=order_id,
            razorpay_payment_id=entity.get("id", ""),
            source=f"webhook:{event}",
        )
    elif event == "payment.failed":
        reason = entity.get("error_description") or entity.get("error_reason") or "declined"
        mark_failed(db, razorpay_order_id=order_id, reason=reason, source=f"webhook:{event}")

    return JSONResponse(content={"status": "ok", "event": event})
