import os
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from alembic import command
from alembic.config import Config

from app.auth import current_user
from app.db import User
from app.routes import (
    health,
    clerk_proxy,
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
)
from app.services.instantly_poller import poll_loop
from app.services.m3_tracking import m3_loop

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gtm")


def _run_migrations() -> None:
    """Apply pending Alembic revisions on startup."""
    cfg_path = Path(__file__).parent / "alembic.ini"
    cfg = Config(str(cfg_path))
    cfg.set_main_option("script_location", str(cfg_path.parent / "alembic"))
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


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
    poller = asyncio.create_task(poll_loop())
    m3 = asyncio.create_task(m3_loop())
    log.info("Background tasks started: Instantly poller (1h), M3 tracker (6h)")
    try:
        yield
    finally:
        for t in (poller, m3):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="Agentic GTM Factory API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api"

# Public — no auth required. Mounted at the root (outside /api) so every
# route under /api is guaranteed to require a Clerk session.
app.include_router(health.router)

# Clerk Frontend API proxy — must be public (no auth) and mounted under
# /api so the application router forwards /api/__clerk/* to FastAPI.
app.include_router(clerk_proxy.router, prefix="/api")


@app.get(api_prefix + "/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "email": user.email}


# Authenticated — every route below already declares
# ``user: User = Depends(current_user)`` on each endpoint, which both
# enforces auth and provides the user object. We deliberately avoid
# adding a duplicate router-level ``dependencies=[Depends(current_user)]``
# here so JWKS verification + DB upsert run only once per request.
app.include_router(settings.router, prefix=api_prefix)
app.include_router(strategies.router, prefix=api_prefix)
app.include_router(accounts.router, prefix=api_prefix)
app.include_router(contacts.router, prefix=api_prefix)
app.include_router(signals.router, prefix=api_prefix)
app.include_router(sequences.router, prefix=api_prefix)
app.include_router(copilot.router, prefix=api_prefix)
app.include_router(intelligence.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
