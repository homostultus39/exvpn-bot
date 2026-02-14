from uuid import UUID
from bot.entities.client.service import ClientService
from bot.entities.client.models import ClientResponse
from bot.core.exceptions import UserNotRegisteredException


class UserService:
    def __init__(self, client_service: ClientService):
        self.client_service = client_service

    async def register_user(self, telegram_id: int) -> ClientResponse:
        username = str(telegram_id)
        client = await self.client_service.find_by_username(username)
        if not client:
            client = await self.client_service.create_client(username)
        return client

    async def get_client_id(self, telegram_id: int) -> UUID:
        username = str(telegram_id)
        client = await self.client_service.find_by_username(username)
        if not client:
            raise UserNotRegisteredException(f"User {telegram_id} not registered")
        return client.id

    async def is_registered(self, telegram_id: int) -> bool:
        username = str(telegram_id)
        client = await self.client_service.find_by_username(username)
        return client is not None
