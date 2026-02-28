from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.database.connection import sessionmaker
from bot.database.management.operations.user import get_admin_by_user_id


class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id

        async with sessionmaker() as session:
            admin = await get_admin_by_user_id(session, user_id)

        if not admin:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав администратора")
            else:
                await event.answer("❌ У вас нет прав администратора", show_alert=True)
            return

        return await handler(event, data)
