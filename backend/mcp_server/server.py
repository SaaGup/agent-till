"""Agent-callable surface for the merchant.

Every tool here is a thin adapter over the same plain service functions the REST API uses —
no business logic lives in this file. That keeps the MCP layer swappable: if the transport
misbehaves, these functions can be handed to the model directly with no logic changes.
"""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from app.catalog.service import get_product as _get_product
from app.catalog.service import search_catalog as _search_catalog
from app.db import SessionLocal
from app.payments.service import PaymentError, create_payment_intent, get_order_status

mcp = FastMCP("razorpay-agent-storefront")

SESSION_HEADER = "x-session-id"
CORRELATION_HEADER = "x-correlation-id"


class MissingSession(Exception):
    pass


def _caller_session_id() -> str:
    """Session identity comes from the transport, never from the model.

    It was briefly a tool parameter, and the agent promptly invented its own value
    ('session-velocity-road-runner-1') instead of passing the real one. Since the cumulative
    spend cap and the first-time-buyer gate both key off this id, a model that chooses it gets
    a fresh ₹0 budget on every order — the cap becomes decorative. Binding it to the connection
    puts it out of the model's reach entirely.
    """
    headers = get_http_headers()
    session_id = headers.get(SESSION_HEADER, "").strip()
    if not session_id:
        raise MissingSession("No session bound to this MCP connection.")
    return session_id[:64]


def _caller_correlation_id() -> str | None:
    """Ties every tool call in one agent turn — including a failure and the retry that
    recovers from it — to a single chain in the audit trail."""
    return get_http_headers().get(CORRELATION_HEADER, "").strip()[:36] or None


@mcp.tool()
def search_catalog(
    query: str,
    max_price_inr: float | None = None,
    category: str | None = None,
    limit: int = 5,
) -> dict:
    """Search the merchant's product catalog.

    Args:
        query: Free-text search over product name, description, category and tags.
        max_price_inr: Optional maximum unit price in rupees.
        category: Optional exact category filter (footwear, accessories, apparel, electronics).
        limit: Maximum number of products to return.
    """
    with SessionLocal() as db:
        return {"products": _search_catalog(db, query, max_price_inr, category, limit)}


@mcp.tool()
def get_product(product_id: str) -> dict:
    """Fetch full detail for one product, including live stock quantity.

    Args:
        product_id: The product's catalog id.
    """
    with SessionLocal() as db:
        product = _get_product(db, product_id)
        if product is None:
            return {"error": f"PRODUCT_NOT_FOUND: {product_id}"}
        return product


@mcp.tool()
def create_payment_intent_tool(
    items: list[dict],
    requested_discount_pct: float = 0.0,
) -> dict:
    """Create a payment intent for the current shopper's cart. Prices are always recomputed
    server-side from the catalog — never pass or assume a price. The merchant's policy engine
    may cap the discount, require human approval, or block the order outright; the response
    explains what happened.

    Args:
        items: Cart lines, each {"product_id": str, "qty": int}.
        requested_discount_pct: Discount to request, subject to the merchant's policy cap.
    """
    with SessionLocal() as db:
        try:
            return create_payment_intent(
                db,
                session_id=_caller_session_id(),
                items=items,
                requested_discount_pct=requested_discount_pct,
                correlation_id=_caller_correlation_id(),
            )
        except MissingSession as e:
            return {"error": f"NO_SESSION: {e}"}
        except PaymentError as e:
            return {"error": f"{e.code}: {e.message}"}


@mcp.tool()
def confirm_payment(intent_id: str) -> dict:
    """Check whether a payment intent has completed. Payment itself is completed by the human
    in Razorpay Checkout — card details never reach this agent or the merchant's server — so
    this reports status rather than charging anything.

    Args:
        intent_id: The intent id returned by create_payment_intent_tool.
    """
    with SessionLocal() as db:
        try:
            return get_order_status(db, intent_id)
        except PaymentError as e:
            return {"error": f"{e.code}: {e.message}"}


@mcp.tool()
def get_order_status_tool(intent_id: str) -> dict:
    """Look up the current status of an order.

    Args:
        intent_id: The intent id returned by create_payment_intent_tool.
    """
    with SessionLocal() as db:
        try:
            return get_order_status(db, intent_id)
        except PaymentError as e:
            return {"error": f"{e.code}: {e.message}"}
