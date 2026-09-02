"""The approval gate is the human-in-the-loop control the design rests on. If its endpoint is
reachable without a merchant session, anyone who finds the public URL can approve their own
orders and the gate is theatre."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.service import (
    authenticate,
    create_token,
    decode_token,
    hash_password,
    seed_demo_merchant,
    verify_password,
)
from app.config import settings
from app.models import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_demo_merchant(session)
    yield session
    session.close()


def test_password_round_trip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_hash_is_salted_so_equal_passwords_differ():
    assert hash_password("same") != hash_password("same")


def test_overlong_password_is_rejected_not_silently_truncated():
    """bcrypt ignores everything past 72 bytes, which would make a long password weaker than
    it looks."""
    with pytest.raises(ValueError):
        hash_password("x" * 100)


def test_authenticate_accepts_seeded_merchant(db):
    user = authenticate(db, settings.demo_merchant_email, settings.demo_merchant_password)
    assert user is not None
    assert user.role == "merchant"


def test_authenticate_rejects_bad_password(db):
    assert authenticate(db, settings.demo_merchant_email, "nope") is None


def test_authenticate_is_case_insensitive_on_email(db):
    assert authenticate(db, settings.demo_merchant_email.upper(), settings.demo_merchant_password)


def test_unknown_email_returns_none_rather_than_raising(db):
    assert authenticate(db, "nobody@example.com", "whatever") is None


def test_token_round_trip(db):
    user = authenticate(db, settings.demo_merchant_email, settings.demo_merchant_password)
    claims = decode_token(create_token(user))
    assert claims["sub"] == user.id
    assert claims["role"] == "merchant"


def test_tampered_token_is_rejected(db):
    user = authenticate(db, settings.demo_merchant_email, settings.demo_merchant_password)
    token = create_token(user)
    assert decode_token(token[:-4] + "AAAA") is None


def test_seed_is_idempotent(db):
    from app.models import User

    seed_demo_merchant(db)
    seed_demo_merchant(db)
    assert db.query(User).count() == 1


@pytest.fixture(scope="module")
def client():
    """One client for the module: starting and stopping the app lifespan per test tore down
    anyio's portal and every later shutdown failed."""
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_approval_decision_requires_authentication(client):
    assert client.post("/api/approvals/some-id/decision", json={"approve": True}).status_code == 401


def test_pending_approvals_require_authentication(client):
    assert client.get("/api/approvals").status_code == 401


def test_garbage_bearer_token_is_rejected(client):
    r = client.get("/api/approvals", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_login_succeeds_and_unlocks_approvals(client):
    r = client.post(
        "/api/auth/login",
        json={
            "email": settings.demo_merchant_email,
            "password": settings.demo_merchant_password,
        },
    )
    assert r.status_code == 200
    token = r.json()["token"]
    assert client.get("/api/approvals", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_login_with_wrong_password_is_401_and_leaks_nothing(client):
    r = client.post(
        "/api/auth/login",
        json={"email": settings.demo_merchant_email, "password": "wrong"},
    )
    assert r.status_code == 401
    # Same message for unknown account and wrong password, so responses can't enumerate users.
    assert r.json()["detail"] == "Incorrect email or password."

    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "wrong"}
    )
    assert unknown.json()["detail"] == r.json()["detail"]
