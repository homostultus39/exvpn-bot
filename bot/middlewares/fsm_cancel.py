from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


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


async def cancel_active_fsm(state: FSMContext, bot: Bot) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    data = await state.get_data()
    if "prompt_msg_id" in data and "prompt_chat_id" in data:
        try:
            await bot.delete_message(data["prompt_chat_id"], data["prompt_msg_id"])
        except Exception:
            pass
    await state.clear()


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
