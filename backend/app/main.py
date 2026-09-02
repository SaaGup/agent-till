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
from app.auth.service import seed_demo_merchant
from app.routers import auth, chat, dashboard, payments

configure_logging()
log = logging.getLogger(__name__)


DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-in-production"


def _check_production_secrets() -> None:
    """Refuse to boot a production deployment on the development signing key. A weak JWT secret
    means anyone can mint a merchant session and approve their own orders — better to fail loudly
    at startup than to serve traffic with the approval gate quietly wide open."""
    if settings.environment != "production":
        return
    problems = []
    if settings.jwt_secret == DEV_JWT_SECRET or len(settings.jwt_secret) < 32:
        problems.append("JWT_SECRET must be set to a random value of at least 32 characters")
    if settings.demo_key in {"", "change-me"}:
        problems.append("DEMO_KEY must be set to a non-default value")
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


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
    _check_production_secrets()
    _run_migrations()
    with SessionLocal() as db:
        inserted = seed_catalog(db)
        seed_demo_merchant(db)

    # The MCP tool surface runs inside this process on loopback only: the agents that call it
    # live here too, so it never needs a public port.
    mcp_task = None
    if settings.enable_mcp_server:
        from mcp_server.server import mcp

        mcp_task = asyncio.create_task(
            mcp.run_async(transport="streamable-http", host="127.0.0.1", port=settings.mcp_port)
        )
    log.info("startup complete", extra={"seeded_products": inserted, "env": settings.environment})
    yield
    if mcp_task is not None:
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

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "version": app.version}
