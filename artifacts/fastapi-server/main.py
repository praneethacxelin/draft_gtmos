import os
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic import command
from alembic.config import Config

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
)
from app.services.instantly_poller import poll_loop

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
    _run_migrations()
    log.info("Alembic migrations applied")
    poller = asyncio.create_task(poll_loop())
    log.info("Instantly engagement poller started")
    try:
        yield
    finally:
        poller.cancel()
        try:
            await poller
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
app.include_router(health.router, prefix=api_prefix)
app.include_router(settings.router, prefix=api_prefix)
app.include_router(strategies.router, prefix=api_prefix)
app.include_router(accounts.router, prefix=api_prefix)
app.include_router(contacts.router, prefix=api_prefix)
app.include_router(signals.router, prefix=api_prefix)
app.include_router(sequences.router, prefix=api_prefix)
app.include_router(copilot.router, prefix=api_prefix)
app.include_router(intelligence.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
