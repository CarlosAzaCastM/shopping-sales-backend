"""Catálogo de nombres de producto para el autocompletado.

Un producto "viejo" debe seguir sugiriéndose aunque ya no esté en la lista de
compras, así que el catálogo se alimenta de las **dos** tablas:

- `shopping_items`: lo que compras  -> precio de compra.
- `sales`: lo que vendes            -> precio de compra y precio de venta.

Los nombres se normalizan con ``lower(btrim(name))`` para no duplicar "Leche" y
"leche ". De cada nombre se conserva la escritura, la unidad y los precios del
registro más reciente.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from .database import pool

# Una fila por nombre usado, con el precio de compra y el de venta ya separados.
# `last_used` ordena el catálogo: lo último que tocaste aparece primero.
_QUERY = """
    WITH combined AS (
        SELECT name, unit, price AS buy_price, NULL::numeric AS sell_price, created_at
        FROM shopping_items

        UNION ALL

        SELECT name, unit, cost AS buy_price, sale_price, created_at
        FROM sales
    ),
    grouped AS (
        SELECT
            lower(btrim(name)) AS key,
            -- La escritura más reciente gana como forma canónica.
            (array_agg(name ORDER BY created_at DESC))[1] AS name,
            -- La unidad más reciente que no esté vacía.
            (array_agg(NULLIF(btrim(unit), '') ORDER BY created_at DESC)
                FILTER (WHERE NULLIF(btrim(unit), '') IS NOT NULL))[1] AS unit,
            -- El último precio > 0 visto para cada tipo (ignora los 0).
            (array_agg(buy_price ORDER BY created_at DESC)
                FILTER (WHERE buy_price > 0))[1] AS last_price,
            (array_agg(sell_price ORDER BY created_at DESC)
                FILTER (WHERE sell_price > 0))[1] AS last_sale_price,
            MAX(created_at) AS last_used,
            COUNT(*)::int   AS uses
        FROM combined
        GROUP BY key
    )
    SELECT name, unit, last_price, last_sale_price, last_used, uses
    FROM grouped
    {where}
    ORDER BY last_used DESC NULLS LAST, name
    LIMIT ${limit_index}
"""


async def list_product_names(
    *, search: Optional[str] = None, limit: int = 500
) -> list[dict[str, Any]]:
    """Nombres ya usados, con su unidad y precios, para el autocompletado.

    Se alimenta de la lista de compras y de las ventas, así que un producto
    antiguo sigue apareciendo aunque ya no esté en la lista.
    """
    args: list[Any] = []
    where = ""

    if search and search.strip():
        args.append(f"%{search.strip()}%")
        where = f"WHERE name ILIKE ${len(args)}"

    args.append(limit)
    query = _QUERY.format(where=where, limit_index=len(args))

    rows = await pool().fetch(query, *args)
    return [
        {
            "name": row["name"],
            "unit": row["unit"] or "pza",
            "uses": row["uses"] or 1,
            "last_price": row["last_price"] if row["last_price"] is not None else Decimal("0.00"),
            "last_sale_price": (
                row["last_sale_price"] if row["last_sale_price"] is not None else Decimal("0.00")
            ),
        }
        for row in rows
    ]
