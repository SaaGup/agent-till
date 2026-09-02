import hashlib
import hmac
import logging
import uuid

import razorpay
from razorpay.errors import SignatureVerificationError

from app.config import settings

log = logging.getLogger(__name__)


class FakeRazorpayClient:
    """Stand-in used when no Razorpay keys are configured, so the full agent/policy/audit
    flow stays runnable (and testable in CI) without live credentials. Mirrors the shapes
    the real SDK returns. Never used when RAZORPAY_KEY_ID is set."""

    is_fake = True

    def create_order(self, *, amount_paise: int, receipt: str, notes: dict) -> dict:
        return {
            "id": f"order_FAKE{uuid.uuid4().hex[:10]}",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "notes": notes,
        }

    def fetch_order(self, order_id: str) -> dict:
        return {"id": order_id, "status": "created"}

    def fetch_payment(self, payment_id: str) -> dict:
        return {"id": payment_id, "status": "captured"}

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return signature == "fake_signature"

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return True


class RazorpayClient:
    is_fake = False

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str):
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._webhook_secret = webhook_secret

    def create_order(self, *, amount_paise: int, receipt: str, notes: dict) -> dict:
        return self._client.order.create(
            data={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": notes,
            }
        )

    def fetch_order(self, order_id: str) -> dict:
        return self._client.order.fetch(order_id)

    def fetch_payment(self, payment_id: str) -> dict:
        return self._client.payment.fetch(payment_id)

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        try:
            self._client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            return True
        except SignatureVerificationError:
            return False

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        if not self._webhook_secret or not signature:
            return False
        expected = hmac.new(
            self._webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


def build_client() -> RazorpayClient | FakeRazorpayClient:
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        return RazorpayClient(
            settings.razorpay_key_id,
            settings.razorpay_key_secret,
            settings.razorpay_webhook_secret,
        )
    log.warning("razorpay keys not configured; using FakeRazorpayClient (no live payments)")
    return FakeRazorpayClient()


client = build_client()
