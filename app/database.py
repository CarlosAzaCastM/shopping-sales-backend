"""Database connection pool management (asyncpg + PostgreSQL on Railway)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional
from urllib.parse import urlsplit

import asyncpg

logger = logging.getLogger("shopping_list.db")

_pool: Optional[asyncpg.Pool] = None
_connect_lock: Optional[asyncio.Lock] = None


def get_database_url() -> str:
    """Return the PostgreSQL DSN from the environment.

    Railway injects DATABASE_URL automatically when the service is linked to a
    database. Locally we fall back to backend/.env.
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


def database_target() -> dict[str, Any]:
    """Describe where we are trying to connect, WITHOUT the password.

    This is what makes a failed deploy debuggable: the host is almost always the
    problem (`postgres.railway.internal` unreachable vs. the public proxy).
    """
    info: dict[str, Any] = {
        "configured": False,
        "host": None,
        "port": None,
        "database": None,
        "user": None,
        "kind": None,
    }
    try:
        url = get_database_url()
    except RuntimeError:
        return info

    parts = urlsplit(url)
    host = parts.hostname or ""
    info.update(
        {
            "configured": True,
            "host": host,
            "port": parts.port,
            "database": (parts.path or "/").lstrip("/") or None,
            "user": parts.username,
            "kind": (
                "internal" if host.endswith(".railway.internal") else "public-proxy"
            ),
        }
    )
    return info


async def connect() -> asyncpg.Pool:
    """Create the global connection pool (idempotent)."""
    global _pool, _connect_lock
    if _pool is not None:
        return _pool
    if _connect_lock is None:
        _connect_lock = asyncio.Lock()

    async with _connect_lock:
        if _pool is None:
            target = database_target()
            logger.info(
                "Connecting to PostgreSQL at %s:%s/%s (%s)",
                target["host"],
                target["port"],
                target["database"],
                target["kind"],
            )
            _pool = await asyncpg.create_pool(
                dsn=get_database_url(),
                min_size=1,
                max_size=10,
                # Railway's proxy terminates TLS; asyncpg must not demand a cert.
                ssl="prefer",
                command_timeout=30,
            )
    return _pool


async def try_connect() -> bool:
    """Attempt to create the pool, logging instead of raising on failure.

    Used at startup so the container stays up (and /api/health stays reachable)
    even when the database is down or misconfigured.
    """
    try:
        await connect()
        return True
    except Exception as exc:  # noqa: BLE001 - any driver/network error is a diagnosis
        logger.error(
            "Could not connect to PostgreSQL (%s: %s). The API will start anyway; "
            "check DATABASE_URL and /api/health.",
            type(exc).__name__,
            exc,
        )
        return False


async def start_connection_watchdog(interval_seconds: float = 5.0) -> None:
    """Keep retrying in the background until the pool is up.

    Railway's private network and the Postgres service can take a moment to
    become reachable after a deploy, so a single failed attempt at boot should
    not leave the service dead.
    """
    while _pool is None:
        if await try_connect():
            try:
                await init_schema()
                logger.info("Database ready and schema verified.")
            except Exception as exc:  # noqa: BLE001
                logger.error("Schema init failed: %s: %s", type(exc).__name__, exc)
            return
        await asyncio.sleep(interval_seconds)


async def disconnect() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    """Return the live pool, raising if connect() has not succeeded yet."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


async def ping() -> tuple[bool, Optional[str]]:
    """Return (reachable, error_message) for the health endpoint."""
    if _pool is None:
        return False, "pool not initialised"
    try:
        await _pool.fetchval("SELECT 1")
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


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
    # `price` in the shopping list is what you PAID, so fold any legacy `cost`
    # value from the old two-price design into it before dropping that column.
    "ALTER TABLE shopping_items ADD COLUMN IF NOT EXISTS cost NUMERIC(10, 2) DEFAULT 0.0;",
    """
    UPDATE shopping_items
       SET price = cost
     WHERE (price IS NULL OR price = 0)
       AND cost IS NOT NULL
       AND cost <> 0;
    """,
    "ALTER TABLE shopping_items DROP COLUMN IF EXISTS cost;",
    # Unit of measure: kilo, litro, pieza, caja...
    "ALTER TABLE shopping_items ADD COLUMN IF NOT EXISTS unit VARCHAR(32) NOT NULL DEFAULT 'pza';",
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
    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS unit VARCHAR(32) NOT NULL DEFAULT 'pza';",
    "CREATE INDEX IF NOT EXISTS sales_sold_at_idx ON sales (sold_at DESC, id DESC);",
    # Autocompletado: buscar nombres ya usados es un scan por nombre.
    "CREATE INDEX IF NOT EXISTS shopping_items_name_idx ON shopping_items (lower(name));",
    "CREATE INDEX IF NOT EXISTS sales_name_idx ON sales (lower(name));",
)


async def init_schema() -> None:
    """Create tables and add every missing column (idempotent)."""
    async with pool().acquire() as connection:
        for statement in _SCHEMA_STATEMENTS:
            await connection.execute(statement)


async def get_server_version() -> str:
    """Return the PostgreSQL server version, used by the health endpoint."""
    return await pool().fetchval("SHOW server_version")
