from uuid import UUID
from bot.entities.tariff.repository import TariffRepository
from bot.entities.tariff.models import (
    CreateTariffRequest,
    UpdateTariffRequest,
    TariffResponse,
    TariffsListResponse
)


class TariffService:
    def __init__(self, tariff_repository: TariffRepository):
        self.tariff_repository = tariff_repository

    async def create_tariff(self, request: CreateTariffRequest) -> TariffResponse:
        return await self.tariff_repository.create(request)

    async def get_tariff(self, tariff_id: UUID) -> TariffResponse:
        return await self.tariff_repository.get(tariff_id)

    async def get_all_tariffs(self) -> list[TariffResponse]:
        return await self.tariff_repository.list_all()

    async def get_active_tariffs(self) -> TariffsListResponse:
        return await self.tariff_repository.list_active()

    async def update_tariff(self, tariff_id: UUID, request: UpdateTariffRequest) -> TariffResponse:
        return await self.tariff_repository.update(tariff_id, request)

    async def delete_tariff(self, tariff_id: UUID) -> None:
        await self.tariff_repository.delete(tariff_id)

    def get_tariff_price(self, tariff: TariffResponse, payment_method: str = "rub") -> int:
        if payment_method == "stars":
            return tariff.price_stars
        else:
            return tariff.price_rub

    def get_tariff_days(self, tariff: TariffResponse) -> int:
        return tariff.days
