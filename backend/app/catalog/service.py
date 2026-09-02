from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Product


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
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.description.ilike(like),
                Product.category.ilike(like),
            )
        )
    if max_price_inr is not None:
        stmt = stmt.where(Product.price_inr <= max_price_inr)
    if category:
        stmt = stmt.where(Product.category == category)

    results = db.execute(stmt.order_by(Product.price_inr).limit(max(1, min(limit, 20)))).scalars().all()

    # Keyword search on name/description/category alone misses tag-only matches
    # (e.g. "running" lives in tags for accessories), so fall back to a tag scan.
    if not results and query:
        term = query.lower()
        all_products = db.execute(select(Product).order_by(Product.price_inr)).scalars().all()
        results = [
            p
            for p in all_products
            if any(term in t.lower() for t in (p.tags or []))
            and (max_price_inr is None or p.price_inr <= max_price_inr)
            and (category is None or p.category == category)
        ][:limit]

    return [_to_summary(p) for p in results]


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
