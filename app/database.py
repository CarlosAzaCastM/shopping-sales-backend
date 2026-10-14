"""Database connection pool management (asyncpg + PostgreSQL on Railway)."""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


def get_database_url() -> str:
    """Return the PostgreSQL DSN from the environment.

    Railway injects DATABASE_URL automatically. We fall back to the public
    proxy URL only so that a local clone works without extra setup.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
            "and fill in your Railway PostgreSQL connection string."
        )
    # asyncpg accepts postgres:// but not the SQLAlchemy dialect prefix.
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def connect() -> asyncpg.Pool:
    """Create the global connection pool (idempotent)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=get_database_url(),
            min_size=1,
            max_size=10,
            # Railway's proxy terminates TLS; asyncpg must not demand a cert.
            ssl="prefer",
            command_timeout=30,
        )
    return _pool


async def disconnect() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    """Return the live pool, raising if connect() has not run yet."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


# The pre-existing shopping_items table is left exactly as it was; every column
# this app needs beyond the original six is added by the migrations below.
_SCHEMA_STATEMENTS: tuple[str, ...] = (
    # --- shopping list -----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS shopping_items (
        id           SERIAL PRIMARY KEY,
        name         VARCHAR(255)   NOT NULL,
        quantity     INTEGER        DEFAULT 1,
        is_completed BOOLEAN        DEFAULT FALSE,
        created_at   TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
        price        NUMERIC(10, 2) DEFAULT 0.0
    );
    """,
    # Unit cost paid for the product (used to price the shopping list).
    "ALTER TABLE shopping_items ADD COLUMN IF NOT EXISTS cost NUMERIC(10, 2) DEFAULT 0.0;",
    # --- sales -------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS sales (
        id                SERIAL PRIMARY KEY,
        name              VARCHAR(255)   NOT NULL,
        quantity          INTEGER        NOT NULL DEFAULT 1,
        cost              NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
        sale_price        NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
        sold_at           DATE           NOT NULL DEFAULT CURRENT_DATE,
        created_at        TIMESTAMP      DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS sales_sold_at_idx ON sales (sold_at DESC, id DESC);",
)


async def init_schema() -> None:
    """Create tables and add every missing column (idempotent)."""
    async with pool().acquire() as connection:
        for statement in _SCHEMA_STATEMENTS:
            await connection.execute(statement)


async def get_server_version() -> str:
    """Return the PostgreSQL server version, used by the health endpoint."""
    return await pool().fetchval("SHOW server_version")
