"""Shopping list REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from .. import crud
from ..database import database_target, get_server_version, ping
from ..schemas import Health, Item, ItemCreate, ItemUpdate

router = APIRouter(prefix="/api", tags=["items"])


@router.get("/health", response_model=Health)
async def health(response: Response) -> Health:
    """Liveness + database reachability probe.

    Always returns 200 with a JSON body so it is easy to read from a browser or
    the Cloudflare proxy, and reports exactly which host we are talking to
    (never the password) so a bad DATABASE_URL is obvious.
    """
    target = database_target()
    reachable, error = await ping()

    version: str | None = None
    if reachable:
        try:
            version = await get_server_version()
        except Exception:  # noqa: BLE001 - not worth failing health over
            version = None

    if reachable:
        db_status = "ok"
    elif not target["configured"]:
        db_status = "error: DATABASE_URL is not set"
    else:
        db_status = f"error: {error}"

    if not reachable:
        # Surface the real state in the HTTP status too, for uptime monitors.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return Health(
        status="ok",
        database=db_status,
        server_version=version,
        database_host=target["host"],
        database_port=target["port"],
        database_name=target["database"],
        database_kind=target["kind"],
    )


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
