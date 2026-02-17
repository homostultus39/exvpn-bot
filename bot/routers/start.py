from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.user.service import UserService
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.keyboards.user import get_agreement_keyboard, get_main_menu_keyboard
from bot.messages.user import WELCOME_MESSAGE, MAIN_MENU_MESSAGE, CLIENT_INFO
from bot.utils.logger import logger

router = Router()
settings = get_settings()

agreed_users = set()


@router.message(CommandStart())
async def start_command_handler(message: Message):
    telegram_id = message.from_user.id

    if telegram_id in agreed_users:
        await message.answer(
            MAIN_MENU_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer(
            WELCOME_MESSAGE.format(CLIENT_INFO),
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
            user_service = UserService(client_service)

            await user_service.register_user(telegram_id)
            agreed_users.add(telegram_id)

            logger.info(f"User {telegram_id} accepted terms and registered")

            await callback.message.edit_text(
                "✅ Спасибо! Вы приняли условия использования."
            )
            await callback.message.answer(
                MAIN_MENU_MESSAGE,
                reply_markup=get_main_menu_keyboard()
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Failed to register user {telegram_id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery):
    await callback.message.edit_text(MAIN_MENU_MESSAGE)
    await callback.message.answer(
        MAIN_MENU_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()
