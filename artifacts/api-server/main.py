import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gtm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("FastAPI server started")
    yield


app = FastAPI(title="Agentic GTM Factory API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes mount under /api
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
