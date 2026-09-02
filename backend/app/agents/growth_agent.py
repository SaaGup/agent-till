"""The Growth Co-Pilot.

Proposes one complementary add-on for a cart. Whatever discount it asks for is independently
clamped by the policy engine before the shopper ever sees it — the model influences the offer,
it does not set the price.
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import build_llm
from app.agents.prompts import GROWTH_SYSTEM_PROMPT
from app.audit.logger import log_action, new_correlation_id
from app.models import Product
from app.policy.engine import evaluate_discount
from app.policy.rules import PolicyConfig

log = logging.getLogger(__name__)

DEFAULT_REQUESTED_DISCOUNT_PCT = 35.0


def _candidates(db: Session, cart_product_ids: list[str]) -> list[Product]:
    rows = (
        db.execute(
            select(Product)
            .where(Product.category.in_(["accessories", "apparel"]))
            .where(Product.stock_qty > 0)
            .order_by(Product.price_inr)
        )
        .scalars()
        .all()
    )
    return [p for p in rows if p.id not in set(cart_product_ids)][:6]


def _ask_model(candidates: list[Product], buyer_intent_summary: str) -> dict | None:
    llm = build_llm()
    if llm is None:
        return None
    listing = [
        {"id": p.id, "name": p.name, "price_inr": p.price_inr, "tags": p.tags} for p in candidates
    ]
    try:
        raw = llm.complete(
            GROWTH_SYSTEM_PROMPT,
            f"Shopper wants: {buyer_intent_summary}\nCandidates: {json.dumps(listing)}",
        )
        cleaned = raw.strip()
        # Smaller models often wrap JSON in a fence despite being told not to.
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1].removeprefix("json").strip()
        return json.loads(cleaned)
    except Exception:
        log.exception("growth co-pilot model call failed; falling back to a rule")
        return None


def propose_upsell(
    db: Session,
    *,
    session_id: str,
    cart_product_ids: list[str],
    buyer_intent_summary: str,
) -> dict | None:
    cfg = PolicyConfig.from_settings()
    candidates = _candidates(db, cart_product_ids)
    if not candidates:
        return None

    suggestion = _ask_model(candidates, buyer_intent_summary)
    by_id = {p.id: p for p in candidates}

    if suggestion and suggestion.get("product_id") in by_id:
        product = by_id[suggestion["product_id"]]
        requested_pct = float(suggestion.get("requested_discount_pct", DEFAULT_REQUESTED_DISCOUNT_PCT))
        rationale = str(suggestion.get("rationale", "")).strip()
    else:
        # Deterministic fallback keeps the demo intact if the model is unavailable or off-script.
        product = candidates[0]
        requested_pct = DEFAULT_REQUESTED_DISCOUNT_PCT
        rationale = f"{product.name} is frequently bought alongside running shoes."

    discount = evaluate_discount(requested_pct, cfg)
    discounted_price = round(product.price_inr * (1 - discount.capped_pct / 100), 2)

    log_action(
        db,
        session_id=session_id,
        actor="growth_copilot_agent",
        action_type="propose_upsell",
        correlation_id=new_correlation_id(),
        decision="capped" if discount.was_capped else "allowed",
        explanation=discount.explanation,
        input_summary={
            "cart_product_ids": cart_product_ids,
            "requested_discount_pct": discount.requested_pct,
        },
        output_summary={
            "product_id": product.id,
            "applied_discount_pct": discount.capped_pct,
            "rationale": rationale,
        },
        amount_inr=discounted_price,
        policy=cfg,
    )

    return {
        "product_id": product.id,
        "name": product.name,
        "list_price_inr": product.price_inr,
        "discounted_price_inr": discounted_price,
        "requested_discount_pct": discount.requested_pct,
        "capped_discount_pct": discount.capped_pct,
        "was_capped": discount.was_capped,
        "rationale": rationale,
        "explanation": discount.explanation,
    }
