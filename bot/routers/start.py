from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.keyboards.user import get_agreement_keyboard, get_main_menu_keyboard
from bot.messages.user import WELCOME_MESSAGE, MAIN_MENU_MESSAGE, CLIENT_INFO, TRIAL_MESSAGE
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last

router = Router()
settings = get_settings()
logger = configure_logger("START_ROUTER", "green")

agreed_users = set()


@router.message(CommandStart())
async def start_command_handler(message: Message):
    telegram_id = message.from_user.id

    if telegram_id in agreed_users:
        await message.delete()
        await delete_last(message.bot, message.chat.id)
        sent = await message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
        store(message.chat.id, sent.message_id)
    else:
        await message.answer(
            WELCOME_MESSAGE,
            reply_markup=get_agreement_keyboard(settings)
        )


@router.callback_query(F.data == "agree_to_terms")
async def agree_to_terms_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id

    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)

            _, is_new = await client_service.get_or_create_by_telegram_id(telegram_id)
            agreed_users.add(telegram_id)

            logger.info(f"User {telegram_id} accepted terms and registered (new={is_new})")

            await callback.answer("✅ Принято!")
            await callback.message.delete()

            chat_id = callback.message.chat.id
            if is_new:
                sent_trial = await callback.message.answer(TRIAL_MESSAGE)
                sent_info = await callback.message.answer(CLIENT_INFO)
                sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
                store(chat_id, sent_trial.message_id, sent_info.message_id, sent_menu.message_id)
            else:
                sent_info = await callback.message.answer(CLIENT_INFO)
                sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
                store(chat_id, sent_info.message_id, sent_menu.message_id)
    except Exception as e:
        logger.error(f"Failed to register user {telegram_id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery):
    await callback.message.delete()
    sent = await callback.message.answer(
        MAIN_MENU_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )
    store(callback.message.chat.id, sent.message_id)
    await callback.answer()
