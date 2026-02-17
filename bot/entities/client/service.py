from uuid import UUID
from bot.entities.client.repository import ClientRepository
from bot.entities.client.models import (
    CreateClientRequest,
    ClientResponse,
    ClientWithPeersResponse
)
from bot.core.exceptions import SubscriptionExpiredException, UserNotRegisteredException


class ClientService:
    def __init__(self, repository: ClientRepository):
        self.repository = repository

    async def create_client(self, username: str) -> ClientResponse:
        request = CreateClientRequest(username=username)
        return await self.repository.create(request)

    async def get_client(self, client_id: UUID) -> ClientWithPeersResponse:
        return await self.repository.get(client_id)

    async def subscribe(self, client_id: UUID, tariff_code: str) -> ClientResponse:
        return await self.repository.subscribe(client_id, tariff_code)

    async def check_subscription(self, client_id: UUID) -> bool:
        client = await self.repository.get(client_id)
        return client.subscription_status in ["trial", "active"]

    async def ensure_active_subscription(self, client_id: UUID) -> None:
        if not await self.check_subscription(client_id):
            raise SubscriptionExpiredException("Subscription has expired")

    async def find_by_username(self, username: str) -> ClientWithPeersResponse | None:
        return await self.repository.find_by_username(username)

    async def get_or_create_by_telegram_id(self, telegram_id: int) -> ClientResponse:
        username = str(telegram_id)
        client = await self.repository.find_by_username(username)
        if not client:
            client = await self.create_client(username)
        return client

    async def get_client_id_by_telegram_id(self, telegram_id: int) -> UUID:
        username = str(telegram_id)
        client = await self.repository.find_by_username(username)
        if not client:
            raise UserNotRegisteredException(f"User {telegram_id} not registered")
        return client.id

    async def is_registered_by_telegram_id(self, telegram_id: int) -> bool:
        username = str(telegram_id)
        client = await self.repository.find_by_username(username)
        return client is not None
