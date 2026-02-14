from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings


class AdminMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.settings = get_settings()

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id

        if user_id not in self.settings.admin_ids:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав администратора")
            else:
                await event.answer("❌ У вас нет прав администратора", show_alert=True)
            return

        return await handler(event, data)
