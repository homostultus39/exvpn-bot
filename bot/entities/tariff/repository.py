from uuid import UUID
from bot.core.api_client import APIClient
from bot.entities.tariff.models import (
    CreateTariffRequest,
    UpdateTariffRequest,
    TariffResponse,
    TariffsListResponse
)


class TariffRepository:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    async def create(self, request: CreateTariffRequest) -> TariffResponse:
        data = await self.api_client.post("/tariffs/", json=request.model_dump(mode="json"))
        return TariffResponse(**data)

    async def get(self, tariff_id: UUID) -> TariffResponse:
        data = await self.api_client.get(f"/tariffs/{tariff_id}")
        return TariffResponse(**data)

    async def list_all(self) -> list[TariffResponse]:
        data = await self.api_client.get("/tariffs/")
        return [TariffResponse(**item) for item in data]

    async def list_active(self) -> TariffsListResponse:
        data = await self.api_client.get("/tariffs/active")
        return TariffsListResponse(**data)

    async def update(self, tariff_id: UUID, request: UpdateTariffRequest) -> TariffResponse:
        data = await self.api_client.patch(f"/tariffs/{tariff_id}", json=request.model_dump(mode="json", exclude_none=True))
        return TariffResponse(**data)

    async def delete(self, tariff_id: UUID) -> None:
        await self.api_client.delete(f"/tariffs/{tariff_id}")
