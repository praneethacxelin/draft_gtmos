from dotenv import load_dotenv
load_dotenv()

import os as _os
# Allow OPENAI_API_KEY as an alias for the Replit-style env var name.
# The .env ships with OPENAI_API_KEY; llm.py reads AI_INTEGRATIONS_OPENAI_API_KEY.
if not _os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") and _os.environ.get("OPENAI_API_KEY"):
    _os.environ["AI_INTEGRATIONS_OPENAI_API_KEY"] = _os.environ["OPENAI_API_KEY"]

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.services.rate_limit import RateLimitExceeded
from alembic import command
from alembic.config import Config

from app.auth import current_user
from app.db import User
from app.routes import (
    health,
    settings,
    strategies,
    accounts,
    contacts,
    signals,
    sequences,
    copilot,
    intelligence,
    dashboard,
    admin,
    audit,
    analytics,
    experiments,
)
from app.services.instantly_poller import poll_loop
from app.services.m3_tracking import m3_loop
from app.services.signal_cron import signal_cron_loop

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gtm")


def _run_migrations() -> None:
    """Apply pending Alembic revisions on startup."""
    this_dir = Path(__file__).resolve().parent
    cfg_path = this_dir / "alembic.ini"
    cfg = Config(str(cfg_path))
    cfg.set_main_option("script_location", str(this_dir / "alembic"))
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    # configparser treats % as interpolation; escape it so %40 etc. pass through
    cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def _auto_configure_api_keys() -> None:
    """Seed Apollo and Instantly API keys from environment variables.

    Reads ``APOLLO_API_KEY`` and ``INSTANTLY_API_KEY`` from the process
    environment and upserts them into the ``app_settings`` table for the
    shared ``user_public`` user.  This means the user never has to
    manually enter the keys through the Settings UI.
    """
    from app.db import SessionLocal
    from app.services import settings_service

    env_keys = {
        "apollo": os.environ.get("APOLLO_API_KEY"),
        "instantly": os.environ.get("INSTANTLY_API_KEY"),
    }
    db = SessionLocal()
    try:
        for name, key in env_keys.items():
            if key:
                settings_service.upsert_integration(
                    db, "user_public", name, key, is_enabled=True,
                )
                log.info("Auto-configured %s API key from environment", name)
    except Exception as exc:
        log.warning("Failed to auto-configure API keys: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys, traceback
    try:
        _run_migrations()
        log.info("Alembic migrations applied")
    except BaseException as e:
        sys.stderr.write(f"\n!!! MIGRATION FAILED: {type(e).__name__}: {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    # Dispose the connection pool so every subsequent request gets a fresh
    # connection that sees the post-migration schema. Without this, psycopg3's
    # server-side prepared-statement cache can hold a stale column list from
    # before Alembic added new columns (e.g. discovery_data, roi_json).
    from app.db import engine as _engine
    _engine.dispose()
    log.info("Connection pool recycled after migrations")
    _auto_configure_api_keys()
    poller = asyncio.create_task(poll_loop())
    m3 = asyncio.create_task(m3_loop())
    signals = asyncio.create_task(signal_cron_loop())
    log.info("Background tasks started: Instantly poller (1h), M3 tracker (6h), Signal cron (24h)")
    try:
        yield
    finally:
        for t in (poller, m3, signals):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


# Trigger reload - force restart 1
app = FastAPI(
    title="GTMOS Backend",
    description="Agentic GTM Factory API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(int(exc.retry_after))},
        content={
            "detail": str(exc),
            "integration": exc.name,
            "retry_after_seconds": int(exc.retry_after),
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api"

# Public — auth removed. All requests are treated as the same shared
# user (see app.auth.current_user). Routes still take a `user` dep so
# foreign keys keep working but no token is required.
app.include_router(health.router)


@app.get(api_prefix + "/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "email": user.email}


app.include_router(settings.router, prefix=api_prefix)
app.include_router(strategies.router, prefix=api_prefix)
app.include_router(experiments.router, prefix=api_prefix)
app.include_router(accounts.router, prefix=api_prefix)
app.include_router(contacts.router, prefix=api_prefix)
app.include_router(signals.router, prefix=api_prefix)
app.include_router(sequences.router, prefix=api_prefix)
app.include_router(copilot.router, prefix=api_prefix)
app.include_router(intelligence.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
