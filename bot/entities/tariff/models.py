from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class CreateTariffRequest(BaseModel):
    code: str
    name: str
    days: int
    price_rub: int
    price_stars: int
    is_active: bool = True
    sort_order: int = 0


class UpdateTariffRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    days: int | None = None
    price_rub: int | None = None
    price_stars: int | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class TariffResponse(BaseModel):
    id: UUID
    code: str
    name: str
    days: int
    price_rub: int
    price_stars: int
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TariffsListResponse(BaseModel):
    enabled: bool
    tariffs: list[TariffResponse]
