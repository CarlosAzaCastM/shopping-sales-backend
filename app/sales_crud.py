"""CRUD helpers for sales, including the derived margin figures."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import asyncpg

from .database import pool
from .schemas import SaleCreate, SaleUpdate

TABLE = "sales"

_STORED_COLUMNS = "id, name, quantity, cost, sale_price, sold_at, created_at"

# Totals and margin are computed in SQL so every consumer gets identical
# rounding. `cost` and `sale_price` are per-unit.
_DERIVED = """
    (cost * quantity)                          AS total_cost,
    (sale_price * quantity)                    AS total_revenue,
    ((sale_price - cost) * quantity)           AS profit,
    CASE
        WHEN (sale_price * quantity) > 0
        THEN ROUND((((sale_price - cost) * quantity) / (sale_price * quantity) * 100)::numeric, 2)
        ELSE 0
    END                                        AS margin_pct
"""

_SELECT = f"SELECT {_STORED_COLUMNS}, {_DERIVED} FROM {TABLE}"


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    # asyncpg returns Decimal for NUMERIC and date for DATE; Pydantic accepts
    # both, but margin_pct comes back as Decimal and the schema wants a float.
    margin = data.get("margin_pct")
    if isinstance(margin, Decimal):
        data["margin_pct"] = float(margin)
    return data


async def list_sales(*, search: Optional[str] = None) -> list[dict[str, Any]]:
    """Return every sale, most recent first."""
    if search:
        rows = await pool().fetch(
            f"{_SELECT} WHERE name ILIKE $1 ORDER BY sold_at DESC, id DESC",
            f"%{search.strip()}%",
        )
    else:
        rows = await pool().fetch(f"{_SELECT} ORDER BY sold_at DESC, id DESC")
    return [_row_to_dict(row) for row in rows]


async def get_sale(sale_id: int) -> Optional[dict[str, Any]]:
    """Return a single sale with its derived figures, or None."""
    row = await pool().fetchrow(f"{_SELECT} WHERE id = $1", sale_id)
    return _row_to_dict(row) if row else None


async def create_sale(payload: SaleCreate) -> dict[str, Any]:
    """Insert a sale. `sold_at` defaults to today when omitted."""
    row = await pool().fetchrow(
        f"""
        INSERT INTO {TABLE} (name, quantity, cost, sale_price, sold_at)
        VALUES ($1, $2, $3, $4, COALESCE($5, CURRENT_DATE))
        RETURNING {_STORED_COLUMNS}
        """,
        payload.name,
        payload.quantity,
        payload.cost,
        payload.sale_price,
        payload.sold_at,
    )
    assert row is not None
    created = await get_sale(row["id"])
    assert created is not None
    return created


async def update_sale(sale_id: int, payload: SaleUpdate) -> Optional[dict[str, Any]]:
    """Partially update a sale; returns None when the id does not exist."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return await get_sale(sale_id)

    assignments: list[str] = []
    args: list[Any] = []
    for field, value in data.items():
        # COALESCE keeps the NOT NULL default when the client sends null.
        args.append(value)
        assignments.append(f"{field} = COALESCE(${len(args)}, {field})")

    args.append(sale_id)
    result = await pool().fetchrow(
        f"UPDATE {TABLE} SET {', '.join(assignments)} WHERE id = ${len(args)} RETURNING id",
        *args,
    )
    if result is None:
        return None
    return await get_sale(sale_id)


async def delete_sale(sale_id: int) -> bool:
    """Delete a sale; returns True when a row was removed."""
    result = await pool().execute(f"DELETE FROM {TABLE} WHERE id = $1", sale_id)
    return result.endswith(" 1")


async def totals() -> dict[str, Any]:
    """Aggregate every sale into the figures shown on the dashboard."""
    row = await pool().fetchrow(
        f"""
        SELECT
            COUNT(*)                                   AS sales_count,
            COALESCE(SUM(quantity), 0)                 AS units_sold,
            COALESCE(SUM(cost * quantity), 0)          AS total_cost,
            COALESCE(SUM(sale_price * quantity), 0)    AS total_revenue,
            COALESCE(SUM((sale_price - cost) * quantity), 0) AS profit
        FROM {TABLE}
        """
    )
    assert row is not None

    totals = dict(row)
    revenue = Decimal(totals["total_revenue"] or 0)
    profit = Decimal(totals["profit"] or 0)
    totals["margin_pct"] = (
        float(round(profit / revenue * 100, 2)) if revenue > 0 else 0.0
    )

    best = await pool().fetchrow(
        f"""
        SELECT name, ((sale_price - cost) * quantity) AS profit
        FROM {TABLE}
        ORDER BY profit DESC, id DESC
        LIMIT 1
        """
    )
    totals["best_sale_name"] = best["name"] if best else None
    totals["best_sale_profit"] = best["profit"] if best else Decimal("0.00")

    totals["sales_count"] = int(totals["sales_count"] or 0)
    totals["units_sold"] = int(totals["units_sold"] or 0)
    return totals
