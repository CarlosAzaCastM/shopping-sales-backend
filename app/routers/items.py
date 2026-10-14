"""Shopping list REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from .. import crud
from ..database import get_server_version, pool
from ..schemas import Health, Item, ItemCreate, ItemUpdate

router = APIRouter(prefix="/api", tags=["items"])


@router.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness + database reachability probe."""
    version: str | None = None
    try:
        await pool().fetchval("SELECT 1")
        db_status = "ok"
        version = await get_server_version()
    except Exception as exc:  # noqa: BLE001 - report any driver/network error
        db_status = f"error: {exc.__class__.__name__}"
    return Health(status="ok", database=db_status, server_version=version)


@router.get("/items", response_model=list[Item])
async def list_items(
    only_pending: bool = Query(False, description="Hide completed items"),
    search: str | None = Query(None, max_length=255, description="Filter by name"),
) -> list[Item]:
    rows = await crud.list_items(only_pending=only_pending, search=search)
    return [Item(**row) for row in rows]


@router.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate) -> Item:
    row = await crud.create_item(payload)
    return Item(**row)


@router.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int) -> Item:
    row = await crud.get_item(item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} not found")
    return Item(**row)


@router.patch("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, payload: ItemUpdate) -> Item:
    row = await crud.update_item(item_id, payload)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} not found")
    return Item(**row)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int) -> None:
    deleted = await crud.delete_item(item_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} not found")


@router.delete("/items", status_code=status.HTTP_200_OK)
async def clear_completed() -> dict[str, int]:
    """Remove every completed item in one shot."""
    return {"deleted": await crud.clear_completed()}
