"""Merchant authentication.

The approval gate is the human-in-the-loop control the whole design rests on, so the endpoint
that decides approvals cannot be open to anyone who finds the URL. Merchant actions require a
signed session; the shopper-facing chat stays public.
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

log = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=12)


def hash_password(password: str) -> str:
    # bcrypt silently truncates at 72 bytes, so reject rather than accept a password whose
    # tail is ignored.
    if len(password.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user.id, "email": user.email, "role": user.role, "iat": now, "exp": now + TOKEN_TTL},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()
    if user is None:
        # Hash anyway so a missing account and a wrong password take similar time, rather than
        # letting response timing enumerate valid emails.
        bcrypt.checkpw(b"timing", bcrypt.hashpw(b"timing", bcrypt.gensalt()))
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def require_merchant(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Merchant sign-in required.")

    claims = decode_token(header.removeprefix("Bearer ").strip())
    if claims is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    user = db.get(User, claims.get("sub", ""))
    if user is None or user.role != "merchant":
        raise HTTPException(status_code=403, detail="Merchant access required.")
    return user


def seed_demo_merchant(db: Session) -> None:
    """The demo account is intentionally public — judges need to sign in. It is created only
    when no merchant exists, and the password comes from the environment so a real deployment
    can set its own."""
    existing = db.execute(select(User).limit(1)).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        User(
            email=settings.demo_merchant_email.strip().lower(),
            password_hash=hash_password(settings.demo_merchant_password),
            role="merchant",
            display_name="Demo Merchant",
        )
    )
    db.commit()
    log.info("seeded demo merchant", extra={"email": settings.demo_merchant_email})
