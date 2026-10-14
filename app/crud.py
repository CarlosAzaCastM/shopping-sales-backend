"""CRUD helpers for shopping list items."""

from __future__ import annotations

from typing import Any, Optional

import asyncpg

from .database import pool
from .schemas import ItemCreate, ItemUpdate

TABLE = "shopping_items"

_COLUMNS = "id, name, quantity, is_completed, created_at, price, cost"


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


async def list_items(
    *, only_pending: bool = False, search: Optional[str] = None
) -> list[dict[str, Any]]:
    """Return every item, newest first, with optional filters."""
    clauses: list[str] = []
    args: list[Any] = []

    if only_pending:
        clauses.append("is_completed = FALSE")
    if search:
        args.append(f"%{search.strip()}%")
        clauses.append(f"name ILIKE ${len(args)}")

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT {_COLUMNS} FROM {TABLE}{where} ORDER BY is_completed ASC, id DESC"

    rows = await pool().fetch(query, *args)
    return [_row_to_dict(row) for row in rows]


async def get_item(item_id: int) -> Optional[dict[str, Any]]:
    """Return a single item or None."""
    row = await pool().fetchrow(
        f"SELECT {_COLUMNS} FROM {TABLE} WHERE id = $1", item_id
    )
    return _row_to_dict(row) if row else None


async def create_item(payload: ItemCreate) -> dict[str, Any]:
    """Insert a new item and return the stored row."""
    row = await pool().fetchrow(
        f"""
        INSERT INTO {TABLE} (name, quantity, price, cost, is_completed)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING {_COLUMNS}
        """,
        payload.name,
        payload.quantity,
        payload.price,
        payload.cost,
        payload.is_completed,
    )
    assert row is not None  # RETURNING always yields a row on success
    return _row_to_dict(row)


async def update_item(item_id: int, payload: ItemUpdate) -> Optional[dict[str, Any]]:
    """Partially update an item; returns None when the id does not exist."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return await get_item(item_id)

    assignments: list[str] = []
    args: list[Any] = []
    for field, value in data.items():
        args.append(value)
        assignments.append(f"{field} = ${len(args)}")

    args.append(item_id)
    query = (
        f"UPDATE {TABLE} SET {', '.join(assignments)} "
        f"WHERE id = ${len(args)} RETURNING {_COLUMNS}"
    )
    row = await pool().fetchrow(query, *args)
    return _row_to_dict(row) if row else None


async def delete_item(item_id: int) -> bool:
    """Delete an item; returns True when a row was removed."""
    result = await pool().execute(f"DELETE FROM {TABLE} WHERE id = $1", item_id)
    return result.endswith(" 1")


async def clear_completed() -> int:
    """Delete every completed item; returns the number of removed rows."""
    result = await pool().execute(f"DELETE FROM {TABLE} WHERE is_completed = TRUE")
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0
