"""FastAPI ASGI entry point."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of the directory uvicorn was started from.
# On Railway the variables come from the service, so this is a no-op there.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from .database import (  # noqa: E402
    database_target,
    disconnect,
    start_connection_watchdog,
)
from .routers import catalog, items, sales  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shopping_list")


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the API even when PostgreSQL is unreachable.

    Connecting in the background (instead of blocking startup) means a
    misconfigured DATABASE_URL no longer kills the container: the service stays
    up, /api/health reports the exact problem, and the connection recovers on
    its own once the database is reachable.
    """
    target = database_target()
    if not target["configured"]:
        logger.error("DATABASE_URL is not set - the API will run without a database.")
    else:
        logger.info(
            "DATABASE_URL target -> %s:%s/%s (%s)",
            target["host"],
            target["port"],
            target["database"],
            target["kind"],
        )

    watchdog = asyncio.create_task(start_connection_watchdog())
    try:
        yield
    finally:
        watchdog.cancel()
        await disconnect()


app = FastAPI(
    title="Shopping List + Sales API",
    description=(
        "CRUD API for the shopping list and sales register, "
        "backed by PostgreSQL on Railway."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

origins = _allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # When origins is "*" credentials must stay disabled, otherwise the
    # browser rejects the wildcard response.
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)
app.include_router(sales.router)
app.include_router(catalog.router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "shopping-list-api", "docs": "/docs"}
