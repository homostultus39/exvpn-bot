from uuid import UUID
from bot.entities.user.storage import UserStorage
from bot.entities.user.models import BotUser
from bot.entities.client.service import ClientService
from bot.core.exceptions import UserNotRegisteredException


class UserService:
    def __init__(self, storage: UserStorage, client_service: ClientService):
        self.storage = storage
        self.client_service = client_service

    async def register_user(self, telegram_id: int, username: str) -> BotUser:
        existing = await self.storage.get(telegram_id)
        if existing:
            return existing

        client = await self.client_service.find_by_username(username)
        if not client:
            client = await self.client_service.create_client(username)

        return await self.storage.create(telegram_id, client.id)

    async def get_user(self, telegram_id: int) -> BotUser:
        user = await self.storage.get(telegram_id)
        if not user:
            raise UserNotRegisteredException(f"User {telegram_id} not registered")
        return user

    async def is_registered(self, telegram_id: int) -> bool:
        return await self.storage.exists(telegram_id)

    async def accept_terms(self, telegram_id: int) -> None:
        await self.storage.update_agreement(telegram_id)

    async def has_agreed_to_terms(self, telegram_id: int) -> bool:
        user = await self.storage.get(telegram_id)
        return user.agreed_to_terms if user else False

    async def get_client_id(self, telegram_id: int) -> UUID:
        user = await self.get_user(telegram_id)
        return user.client_id
