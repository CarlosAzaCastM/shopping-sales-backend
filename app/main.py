"""FastAPI ASGI entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of the directory uvicorn was started from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from .database import connect, disconnect, init_schema  # noqa: E402
from .routers import items, sales  # noqa: E402


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the PostgreSQL pool and apply the schema migrations."""
    await connect()
    await init_schema()
    try:
        yield
    finally:
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


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "shopping-list-api", "docs": "/docs"}
