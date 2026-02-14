from uuid import UUID
from bot.entities.client.service import ClientService
from bot.entities.subscription.models import TARIFFS


class SubscriptionService:
    def __init__(self, client_service: ClientService):
        self.client_service = client_service

    async def buy_subscription(self, client_id: UUID, tariff_code: str) -> None:
        if tariff_code == "test":
            days = 30
        else:
            tariff = TARIFFS.get(tariff_code)
            if not tariff:
                raise ValueError(f"Invalid tariff code: {tariff_code}")
            days = tariff.days

        await self.client_service.extend_subscription(client_id, days)

    async def extend_subscription(self, client_id: UUID, tariff_code: str) -> None:
        await self.buy_subscription(client_id, tariff_code)

    def get_tariff_price(self, tariff_code: str, payment_method: str = "rub") -> int:
        if tariff_code == "test":
            return 0

        tariff = TARIFFS.get(tariff_code)
        if not tariff:
            raise ValueError(f"Invalid tariff code: {tariff_code}")

        if payment_method == "stars":
            return tariff.stars
        else:
            return tariff.rub

    def get_tariff_days(self, tariff_code: str) -> int:
        if tariff_code == "test":
            return 30

        tariff = TARIFFS.get(tariff_code)
        if not tariff:
            raise ValueError(f"Invalid tariff code: {tariff_code}")

        return tariff.days
