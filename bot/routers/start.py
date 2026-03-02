from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings
from bot.keyboards.user import get_agreement_keyboard, get_main_menu_keyboard
from bot.messages.user import WELCOME_MESSAGE, MAIN_MENU_MESSAGE, CLIENT_INFO
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last
from bot.database.connection import get_session
from bot.database.management.operations.user import (
    get_user_by_user_id,
    get_or_create_user_record,
    make_terms_confirmed,
    set_referrer,
)


router = Router()
settings = get_settings()
logger = configure_logger("START_ROUTER", "green")


@router.message(CommandStart())
async def start_command_handler(message: Message):
    user_id = message.from_user.id
    start_param = None
    message_text = (message.text or "").strip()
    parts = message_text.split(maxsplit=1)
    if len(parts) > 1:
        start_param = parts[1].strip()

    referrer_id = None
    if start_param and start_param.startswith("ref_"):
        ref_value = start_param.removeprefix("ref_")
        if ref_value.isdigit():
            referrer_id = int(ref_value)

    try:
        async with get_session() as session:
            existing_record = await get_user_by_user_id(session, user_id)

            is_confirmed = False
            if existing_record:
                is_confirmed = True if existing_record.aggreed_to_terms else False

            if is_confirmed:
                await message.delete()
                await delete_last(message.bot, message.chat.id)
                sent_info = await message.answer(CLIENT_INFO)
                sent_menu = await message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
                store(message.chat.id, sent_info.message_id, sent_menu.message_id)
            else:
                was_created = existing_record is None
                await get_or_create_user_record(session, user_id)
                if was_created:
                    logger.info(f"User with user_id {user_id} was created")

                if was_created and referrer_id is not None:
                    linked = await set_referrer(session, user_id, referrer_id)
                    if linked:
                        logger.info(f"Referrer {referrer_id} linked for user {user_id}")

                await message.answer(
                    WELCOME_MESSAGE,
                    reply_markup=get_agreement_keyboard(settings)
                )
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

        chat_id = callback.message.chat.id

        sent_info = await callback.message.answer(CLIENT_INFO)
        sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
        store(chat_id, sent_info.message_id, sent_menu.message_id)
    except Exception as e:
        logger.error(f"Failed to make edits in database for {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору", show_alert=True)
