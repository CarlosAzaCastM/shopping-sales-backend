"""Pydantic schemas for the shopping list + sales API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MONEY = Decimal("99999999.99")


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("name must not be blank")
    return cleaned


# --------------------------------------------------------------------------- #
# Shopping list
# --------------------------------------------------------------------------- #


class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1, le=100000)
    #: Lo que pagaste por el producto. En la lista de compras solo existe este
    #: precio (el de venta se registra al vender, en /api/sales).
    price: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    #: Unidad de medida: pza, kg, L, caja...
    unit: str = Field(default="pza", min_length=1, max_length=32)
    is_completed: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("unit")
    @classmethod
    def strip_unit(cls, value: str) -> str:
        cleaned = value.strip()
        # Una unidad vacía no aporta nada; se queda con el valor por defecto.
        return cleaned or "pza"


class ItemCreate(ItemBase):
    """Payload accepted by POST /api/items."""


class ItemUpdate(BaseModel):
    """Payload accepted by PATCH /api/items/{id}; every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int | None = Field(default=None, ge=1, le=100000)
    price: Decimal | None = Field(default=None, ge=0, le=MONEY)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    is_completed: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("unit")
    @classmethod
    def strip_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or "pza"


class Item(ItemBase):
    """A shopping list row as stored in PostgreSQL."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Sales
# --------------------------------------------------------------------------- #


class SaleBase(BaseModel):
    """A sale. ``cost`` and ``sale_price`` are per unit; the API returns the
    derived totals and margin so the UI never recomputes them differently."""

    name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1, le=100000)
    #: Lo que te costó (precio de compra), por unidad.
    cost: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    #: Lo que lo vendiste al público, por unidad.
    sale_price: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    #: Unidad de medida: pza, kg, L, caja...
    unit: str = Field(default="pza", min_length=1, max_length=32)
    sold_at: date | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("unit")
    @classmethod
    def strip_unit(cls, value: str) -> str:
        cleaned = value.strip()
        return cleaned or "pza"


class SaleCreate(SaleBase):
    """Payload accepted by POST /api/sales."""


class SaleUpdate(BaseModel):
    """Payload accepted by PATCH /api/sales/{id}; every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int | None = Field(default=None, ge=1, le=100000)
    cost: Decimal | None = Field(default=None, ge=0, le=MONEY)
    sale_price: Decimal | None = Field(default=None, ge=0, le=MONEY)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    sold_at: date | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("unit")
    @classmethod
    def strip_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or "pza"


class Sale(SaleBase):
    """A sale row plus the figures the dashboard needs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sold_at: date
    created_at: datetime | None = None

    # Derived, computed from the stored values.
    total_cost: Decimal
    total_revenue: Decimal
    profit: Decimal
    margin_pct: float


class SalesSummary(BaseModel):
    """Aggregated sales figures returned by GET /api/sales/summary."""

    sales_count: int
    units_sold: int
    total_cost: Decimal
    total_revenue: Decimal
    profit: Decimal
    margin_pct: float
    best_sale_name: str | None = None
    best_sale_profit: Decimal = Decimal("0.00")


class ProductSuggestion(BaseModel):
    """Un nombre de producto ya usado, para el autocompletado.

    Se alimenta tanto de la lista de compras como de las ventas, así que un
    producto antiguo sigue apareciendo aunque ya no esté en la lista.
    """

    name: str
    #: Unidad usada la última vez con ese nombre (para prellenarla).
    unit: str = "pza"
    #: Cuántas veces se ha usado, para ordenar por relevancia.
    uses: int = 1
    #: Último precio de compra visto, para no volver a teclearlo.
    last_price: Decimal = Decimal("0.00")
    #: Último precio de venta visto (solo lo tienen los productos vendidos).
    last_sale_price: Decimal = Decimal("0.00")


class Health(BaseModel):
    """Health report. Deliberately includes the target host so a bad
    DATABASE_URL is visible in the response (the password never is)."""

    status: str
    database: str
    server_version: str | None = None
    database_host: str | None = None
    database_port: int | None = None
    database_name: str | None = None
    database_kind: str | None = None
