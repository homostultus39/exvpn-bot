from uuid import UUID
from bot.entities.client.service import ClientService
from bot.entities.tariff.service import TariffService
from bot.entities.tariff.models import TariffResponse


class SubscriptionService:
    def __init__(self, client_service: ClientService, tariff_service: TariffService):
        self.client_service = client_service
        self.tariff_service = tariff_service

    async def buy_subscription(self, client_id: UUID, tariff_code: str) -> None:
        await self.client_service.subscribe(client_id, tariff_code)

    async def extend_subscription(self, client_id: UUID, tariff_code: str) -> None:
        await self.buy_subscription(client_id, tariff_code)

    async def get_tariff_by_code(self, tariff_code: str) -> TariffResponse | None:
        tariffs_list = await self.tariff_service.get_active_tariffs()
        for tariff in tariffs_list.tariffs:
            if tariff.code == tariff_code:
                return tariff
        return None

    def get_tariff_price(self, tariff: TariffResponse, payment_method: str = "rub") -> int:
        return self.tariff_service.get_tariff_price(tariff, payment_method)

    def get_tariff_days(self, tariff: TariffResponse) -> int:
        return self.tariff_service.get_tariff_days(tariff)