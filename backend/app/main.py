import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.catalog.data import seed_catalog
from app.config import settings
from app.db import SessionLocal, engine
from app.logging_config import configure_logging
from app.middleware.error_handlers import register_error_handlers
from app.middleware.rate_limit import limiter
from app.models import Base

configure_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        inserted = seed_catalog(db)
    log.info("startup complete", extra={"seeded_products": inserted, "env": settings.environment})
    yield


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "version": app.version}
