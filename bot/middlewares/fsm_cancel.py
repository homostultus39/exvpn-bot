from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.management.fsm_utils import cancel_active_fsm

MENU_BUTTON_TEXTS: frozenset[str] = frozenset({
    # User menu
    "🔑 Получить ключ",
    "👤 Профиль",
    "💎 Подписка",
    "🚨 Сообщение об ошибке",
    # Admin menu
    "🌐 Кластеры",
    "👥 Клиенты",
    "💳 Тарифы",
    "📊 Статистика",
    "📢 Рассылка",
    "📋 Обращения",
    "◀️ Выход из админ-панели",
})


class FsmCancelOnMenuMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.text in MENU_BUTTON_TEXTS:
            state: FSMContext | None = data.get("state")
            bot: Bot | None = data.get("bot")
            if state and bot:
                await cancel_active_fsm(state, bot)
        return await handler(event, data)
