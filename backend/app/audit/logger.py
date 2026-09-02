import logging
import uuid

from sqlalchemy.orm import Session

from app.models import AuditLogEntry
from app.policy.rules import PolicyConfig

log = logging.getLogger(__name__)

MONEY_AFFECTING_ACTIONS = {
    "create_payment_intent",
    "confirm_payment",
    "propose_upsell",
    "policy_decision",
    "approval_requested",
    "approval_decided",
    "payment_failed",
    "payment_retried",
    "payment_confirmed",
    "webhook_received",
    "session_spend_cap_blocked",
}


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def log_action(
    db: Session,
    *,
    session_id: str,
    actor: str,
    action_type: str,
    correlation_id: str,
    explanation: str,
    decision: str = "n/a",
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    policy: PolicyConfig | None = None,
    amount_inr: float | None = None,
    order_id: str | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        correlation_id=correlation_id,
        session_id=session_id,
        actor=actor,
        action_type=action_type,
        money_affecting=action_type in MONEY_AFFECTING_ACTIONS,
        input_summary=input_summary or {},
        output_summary=output_summary or {},
        policy_snapshot=policy.as_snapshot() if policy else {},
        decision=decision,
        explanation=explanation,
        amount_inr=amount_inr,
        order_id=order_id,
    )
    db.add(entry)
    db.commit()
    log.info(
        "audit",
        extra={
            "action_type": action_type,
            "actor": actor,
            "decision": decision,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "amount_inr": amount_inr,
        },
    )
    return entry
