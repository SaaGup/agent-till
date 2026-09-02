from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.service import authenticate, create_token, require_merchant
from app.db import get_db
from app.middleware.rate_limit import limiter
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Per-IP. Judges behind one office NAT share a bucket, and a fumbled password should not
# lock the room out of a live demo.
LOGIN_LIMIT = "30/minute"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
@limiter.limit(LOGIN_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = authenticate(db, body.email, body.password)
    if user is None:
        # One message for both wrong-email and wrong-password, so the response can't be used
        # to work out which accounts exist.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return {
        "token": create_token(user),
        "user": {"email": user.email, "role": user.role, "display_name": user.display_name},
    }


@router.get("/me")
def me(user: User = Depends(require_merchant)) -> dict:
    return {"email": user.email, "role": user.role, "display_name": user.display_name}
