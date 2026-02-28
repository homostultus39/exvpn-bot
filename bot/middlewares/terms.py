from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.database.connection import get_session
from bot.database.management.operations.user import get_user_by_user_id


class AcceptedTermsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id

        async with get_session() as session:
            user = await get_user_by_user_id(session, user_id)

        if not user or not user.aggreed_to_terms:
            if isinstance(event, Message):
                await event.answer("❌ Вы не приняли условия использования")
            else:
                await event.answer("❌ Вы не приняли условия использования", show_alert=True)
            return

        return await handler(event, data)
