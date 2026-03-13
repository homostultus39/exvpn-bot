from aiogram import Router
from aiogram.types import CallbackQuery

from bot.database.connection import get_session
from bot.database.management.operations.user import get_user_by_user_id
from bot.management.logger import configure_logger
from bot.management.navigation import show_main_menu, show_welcome_message

router = Router()
logger = configure_logger("LEGACY_CALLBACKS", "yellow")


@router.callback_query()
async def legacy_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    try:
        await callback.answer(
            "Кнопка из старой версии интерфейса. Отправляю актуальное меню.",
            show_alert=True,
        )

        async with get_session() as session:
            user = await get_user_by_user_id(session, user_id)

        if user and user.aggreed_to_terms:
            await show_main_menu(callback.message, clear_tracked=True)
        else:
            await show_welcome_message(callback.message)

        logger.info(f"Refreshed legacy interface for user {user_id}")
    except Exception as error:
        logger.error(f"Failed to refresh legacy interface for user {user_id}: {error}")
        await callback.answer(
            "❌ Не удалось обновить интерфейс. Попробуйте команду /start.",
            show_alert=True,
        )
