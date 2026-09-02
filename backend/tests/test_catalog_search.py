import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.catalog.data import seed_catalog
from app.catalog.service import search_catalog
from app.models import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_catalog(session)
    yield session
    session.close()


def test_running_shoes_query_returns_footwear_not_accessories(db):
    """Regression: the socks description mentions 'running shoes', so a substring search
    surfaced socks ahead of actual shoes."""
    results = search_catalog(db, "I need running shoes", max_price_inr=3000)
    assert results, "expected matches"
    assert results[0]["category"] == "footwear"


def test_price_filter_is_respected(db):
    results = search_catalog(db, "running shoes", max_price_inr=2000)
    assert all(r["price_inr"] <= 2000 for r in results)


def test_category_filter_is_respected(db):
    results = search_catalog(db, "running", category="accessories")
    assert results
    assert all(r["category"] == "accessories" for r in results)


def test_tag_only_match_is_found(db):
    results = search_catalog(db, "hydration")
    assert any(r["id"] == "bottle-hydro-449" for r in results)


def test_nonsense_query_returns_nothing(db):
    assert search_catalog(db, "helicopter parts") == []


def test_limit_is_capped(db):
    assert len(search_catalog(db, "running", limit=2)) <= 2
