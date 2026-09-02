import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.catalog.data import seed_catalog
from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.middleware.error_handlers import register_error_handlers
from app.middleware.rate_limit import limiter
from app.payments import webhooks
from app.routers import chat, dashboard, payments

configure_logging()
log = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Schema changes ship as migrations, not create_all — on a hosted database the schema has
    to move forward without dropping what's already there."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    with SessionLocal() as db:
        inserted = seed_catalog(db)

    # The MCP tool surface runs inside this process on loopback only: the agents that call it
    # live here too, so it never needs a public port.
    from mcp_server.server import mcp

    mcp_task = asyncio.create_task(
        mcp.run_async(transport="streamable-http", host="127.0.0.1", port=settings.mcp_port)
    )
    log.info("startup complete", extra={"seeded_products": inserted, "env": settings.environment})
    yield
    mcp_task.cancel()
    try:
        await mcp_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Agent-Ready Storefront",
    description="A merchant backend transactable by AI buyers, with bounded and audited money actions.",
    version="0.1.0",
    lifespan=lifespan,
    debug=False,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origin.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
register_error_handlers(app)

app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "version": app.version}
