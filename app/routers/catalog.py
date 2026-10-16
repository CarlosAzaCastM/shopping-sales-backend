"""Autocompletado de productos.

Expone los nombres que ya se han usado, tomados tanto de la lista de compras
como de las ventas. El frontend los ofrece en los formularios para no volver a
teclear un producto que ya existe.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import catalog
from ..schemas import ProductSuggestion

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/product-names", response_model=list[ProductSuggestion])
async def product_names(
    search: str | None = Query(
        None, max_length=255, description="Filtra por coincidencia en el nombre"
    ),
    limit: int = Query(500, ge=1, le=2000, description="Máximo de sugerencias"),
) -> list[ProductSuggestion]:
    """Nombres de producto ya usados, más recientes primero."""
    rows = await catalog.list_product_names(search=search, limit=limit)
    return [ProductSuggestion(**row) for row in rows]
