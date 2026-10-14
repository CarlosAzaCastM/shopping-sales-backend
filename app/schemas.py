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
    price: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    cost: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    is_completed: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _clean_name(value)


class ItemCreate(ItemBase):
    """Payload accepted by POST /api/items."""


class ItemUpdate(BaseModel):
    """Payload accepted by PATCH /api/items/{id}; every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int | None = Field(default=None, ge=1, le=100000)
    price: Decimal | None = Field(default=None, ge=0, le=MONEY)
    cost: Decimal | None = Field(default=None, ge=0, le=MONEY)
    is_completed: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


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
    cost: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    sale_price: Decimal = Field(default=Decimal("0.00"), ge=0, le=MONEY)
    sold_at: date | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _clean_name(value)


class SaleCreate(SaleBase):
    """Payload accepted by POST /api/sales."""


class SaleUpdate(BaseModel):
    """Payload accepted by PATCH /api/sales/{id}; every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int | None = Field(default=None, ge=1, le=100000)
    cost: Decimal | None = Field(default=None, ge=0, le=MONEY)
    sale_price: Decimal | None = Field(default=None, ge=0, le=MONEY)
    sold_at: date | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


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


class Health(BaseModel):
    status: str
    database: str
    server_version: str | None = None
