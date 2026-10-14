"""Sales REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from .. import sales_crud as crud
from ..schemas import Sale, SaleCreate, SaleUpdate, SalesSummary

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("/summary", response_model=SalesSummary)
async def sales_summary() -> SalesSummary:
    """Totals across every sale: cost, revenue, profit and margin.

    Declared before `/{sale_id}` so the literal path wins the match.
    """
    return SalesSummary(**await crud.totals())


@router.get("", response_model=list[Sale])
async def list_sales(
    search: str | None = Query(None, max_length=255, description="Filter by name"),
) -> list[Sale]:
    rows = await crud.list_sales(search=search)
    return [Sale(**row) for row in rows]


@router.post("", response_model=Sale, status_code=status.HTTP_201_CREATED)
async def create_sale(payload: SaleCreate) -> Sale:
    row = await crud.create_sale(payload)
    return Sale(**row)


@router.get("/{sale_id}", response_model=Sale)
async def get_sale(sale_id: int) -> Sale:
    row = await crud.get_sale(sale_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sale {sale_id} not found")
    return Sale(**row)


@router.patch("/{sale_id}", response_model=Sale)
async def update_sale(sale_id: int, payload: SaleUpdate) -> Sale:
    row = await crud.update_sale(sale_id, payload)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sale {sale_id} not found")
    return Sale(**row)


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(sale_id: int) -> None:
    if not await crud.delete_sale(sale_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sale {sale_id} not found")
