from datetime import datetime, timedelta
from uuid import UUID
from bot.entities.client.repository import ClientRepository
from bot.entities.client.models import (
    CreateClientRequest,
    UpdateClientRequest,
    ClientResponse,
    ClientWithPeersResponse
)
from bot.core.exceptions import SubscriptionExpiredException


class ClientService:
    def __init__(self, repository: ClientRepository):
        self.repository = repository

    async def create_client(self, username: str, days: int = 30) -> ClientResponse:
        expires_at = datetime.utcnow() + timedelta(days=days)
        request = CreateClientRequest(username=username, expires_at=expires_at)
        return await self.repository.create(request)

    async def get_client(self, client_id: UUID) -> ClientWithPeersResponse:
        return await self.repository.get(client_id)

    async def extend_subscription(self, client_id: UUID, days: int) -> ClientResponse:
        client = await self.repository.get(client_id)
        if client.expires_at > datetime.utcnow():
            new_expires_at = client.expires_at + timedelta(days=days)
        else:
            new_expires_at = datetime.utcnow() + timedelta(days=days)

        request = UpdateClientRequest(expires_at=new_expires_at)
        return await self.repository.update(client_id, request)

    async def check_subscription(self, client_id: UUID) -> bool:
        client = await self.repository.get(client_id)
        return client.expires_at > datetime.utcnow()

    async def ensure_active_subscription(self, client_id: UUID) -> None:
        if not await self.check_subscription(client_id):
            raise SubscriptionExpiredException("Subscription has expired")

    async def find_by_username(self, username: str) -> ClientWithPeersResponse | None:
        return await self.repository.find_by_username(username)
