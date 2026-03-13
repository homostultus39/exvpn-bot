from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.management.navigation import show_main_menu, show_welcome_message
from bot.management.logger import configure_logger
from bot.management.message_tracker import delete_last
from bot.database.connection import get_session
from bot.database.management.operations.user import (
    get_user_by_user_id,
    get_or_create_user_record,
    make_terms_confirmed,
    set_referrer,
)


router = Router()
logger = configure_logger("START_ROUTER", "green")


def _extract_start_param(message_text: str) -> str | None:
    parts = message_text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    start_param = parts[1].strip()
    return start_param or None


@router.message(CommandStart())
async def start_command_handler(message: Message):
    user_id = message.from_user.id
    start_param = _extract_start_param(message.text or "")

    referrer_id = None
    if start_param and start_param.startswith("ref_"):
        ref_value = start_param.removeprefix("ref_")
        if ref_value.isdigit():
            referrer_id = int(ref_value)
    should_refresh_menu = start_param == "true"

    try:
        async with get_session() as session:
            existing_record = await get_user_by_user_id(session, user_id)

            is_confirmed = False
            if existing_record:
                is_confirmed = True if existing_record.aggreed_to_terms else False

            if is_confirmed:
                await message.delete()
                await show_main_menu(message, clear_tracked=True)
                if should_refresh_menu:
                    logger.info(f"Forced menu refresh requested by user {user_id}")
            else:
                was_created = existing_record is None
                await get_or_create_user_record(session, user_id)
                if was_created:
                    logger.info(f"User with user_id {user_id} was created")

                if was_created and referrer_id is not None:
                    linked = await set_referrer(session, user_id, referrer_id)
                    if linked:
                        logger.info(f"Referrer {referrer_id} linked for user {user_id}")

                await show_welcome_message(message)
    except Exception as e:
        logger.error(f"Failed to get or create user with user_id {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору")


@router.callback_query(F.data == "agree_to_terms")
async def agree_to_terms_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    try:
        async with get_session() as session:
            await make_terms_confirmed(session, user_id)

        logger.info(f"User with user_id {user_id} accepted terms")

        await callback.answer("✅ Принято!")
        await callback.message.delete()

        await show_main_menu(callback.message)
    except Exception as e:
        logger.error(f"Failed to make edits in database for {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору", show_alert=True)
