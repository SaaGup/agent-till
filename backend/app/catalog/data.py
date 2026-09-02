import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Product

SEED_PATH = Path(__file__).resolve().parents[2] / "seed_data" / "catalog.json"


def seed_catalog(db: Session) -> int:
    """Idempotent: inserts any seed products missing from the DB, leaves existing rows
    (including demo-mutated stock levels) untouched."""
    products = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing_ids = {row[0] for row in db.query(Product.id).all()}
    inserted = 0
    for p in products:
        if p["id"] in existing_ids:
            continue
        db.add(Product(**p))
        inserted += 1
    if inserted:
        db.commit()
    return inserted
