import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product

# Shopper phrasing ("I need running shoes under 3000") carries filler that would otherwise
# match everything or nothing.
STOPWORDS = {
    "a", "an", "the", "i", "need", "want", "looking", "for", "under", "below", "less",
    "than", "some", "me", "my", "with", "and", "or", "of", "to", "in", "on", "please",
    "show", "find", "get", "buy", "rs", "inr", "rupees", "budget", "around", "about",
    "good", "best", "any", "something", "pair", "new",
}

NAME_WEIGHT = 3
TAG_WEIGHT = 3
CATEGORY_WEIGHT = 2
DESCRIPTION_WEIGHT = 1


def _tokenize(query: str) -> list[str]:
    words = re.findall(r"[a-z]+", query.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _score(product: Product, tokens: list[str]) -> int:
    if not tokens:
        return 1
    name = product.name.lower()
    description = (product.description or "").lower()
    category = product.category.lower()
    tags = [t.lower() for t in (product.tags or [])]

    score = 0
    matched_tokens = 0
    for token in tokens:
        # Each token contributes its single best field match, not the sum across fields.
        # Summing let one token ("running", hitting name + tag + description on socks)
        # outweigh a product matching every token — which ranked socks above shoes.
        best = 0
        if token in name:
            best = max(best, NAME_WEIGHT)
        if any(token in tag for tag in tags):
            best = max(best, TAG_WEIGHT)
        if token in category:
            best = max(best, CATEGORY_WEIGHT)
        if token in description:
            best = max(best, DESCRIPTION_WEIGHT)
        if best:
            matched_tokens += 1
        score += best

    # Matching every token beats matching one token strongly.
    if matched_tokens == len(tokens) and len(tokens) > 1:
        score += 2
    return score


def _to_summary(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "price_inr": p.price_inr,
        "category": p.category,
        "in_stock": p.stock_qty > 0,
        "tags": p.tags,
    }


def search_catalog(
    db: Session,
    query: str,
    max_price_inr: float | None = None,
    category: str | None = None,
    limit: int = 5,
) -> list[dict]:
    stmt = select(Product)
    if max_price_inr is not None:
        stmt = stmt.where(Product.price_inr <= max_price_inr)
    if category:
        stmt = stmt.where(Product.category == category)
    candidates = db.execute(stmt).scalars().all()

    tokens = _tokenize(query)
    # Ranked in Python rather than SQL: the catalog is small, and relevance here needs
    # per-field weighting (a name/tag hit beats an incidental description mention) that a
    # LIKE query can't express.
    scored = [(p, _score(p, tokens)) for p in candidates]
    matched = [(p, s) for p, s in scored if s > 0]
    matched.sort(key=lambda pair: (-pair[1], pair[0].price_inr))

    limit = max(1, min(limit, 20))
    return [_to_summary(p) for p, _ in matched[:limit]]


def get_product(db: Session, product_id: str) -> dict | None:
    p = db.get(Product, product_id)
    if p is None:
        return None
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price_inr": p.price_inr,
        "category": p.category,
        "stock_qty": p.stock_qty,
        "tags": p.tags,
    }
