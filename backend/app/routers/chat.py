import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.buyer_agent import MAX_MESSAGE_CHARS, reset_session, run_buyer_turn
from app.agents.growth_agent import propose_upsell
from app.db import get_db
from app.middleware.rate_limit import CHAT_LIMIT, limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class UpsellRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    cart_product_ids: list[str] = Field(default_factory=list, max_length=10)
    buyer_intent_summary: str = Field(default="", max_length=500)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/chat")
@limiter.limit(CHAT_LIMIT)
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        async for event in run_buyer_turn(body.session_id, body.message):
            yield _sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/upsell")
@limiter.limit(CHAT_LIMIT)
def upsell(request: Request, body: UpsellRequest, db: Session = Depends(get_db)) -> dict:
    proposal = propose_upsell(
        db,
        session_id=body.session_id,
        cart_product_ids=body.cart_product_ids,
        buyer_intent_summary=body.buyer_intent_summary,
    )
    return {"proposal": proposal}


@router.post("/chat/reset")
def reset(body: UpsellRequest) -> dict:
    reset_session(body.session_id)
    return {"status": "reset"}
