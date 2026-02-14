from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.user.storage import UserStorage
from bot.entities.user.service import UserService
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.keyboards.user import get_agreement_keyboard, get_main_menu_keyboard
from bot.messages.user import WELCOME_MESSAGE, MAIN_MENU_MESSAGE
from bot.utils.logger import logger

router = Router()
settings = get_settings()


async def get_user_service() -> UserService:
    storage = UserStorage(settings.database_path)
    await storage.init_db()

    api_client = get_api_client()
    async with api_client:
        client_repo = ClientRepository(api_client)
        client_service = ClientService(client_repo)
        return UserService(storage, client_service)


@router.message(CommandStart())
async def start_command_handler(message: Message):
    telegram_id = message.from_user.id
    username = message.from_user.username or f"user_{telegram_id}"

    user_service = await get_user_service()

    if await user_service.is_registered(telegram_id):
        if await user_service.has_agreed_to_terms(telegram_id):
            await message.answer(
                MAIN_MENU_MESSAGE,
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await message.answer(
                WELCOME_MESSAGE,
                reply_markup=get_agreement_keyboard(settings)
            )
    else:
        try:
            await user_service.register_user(telegram_id, username)
            logger.info(f"User {telegram_id} ({username}) registered")
            await message.answer(
                WELCOME_MESSAGE,
                reply_markup=get_agreement_keyboard(settings)
            )
        except Exception as e:
            logger.error(f"Failed to register user {telegram_id}: {e}")
            await message.answer("❌ Произошла ошибка при регистрации. Попробуйте позже.")


@router.callback_query(F.data == "agree_to_terms")
async def agree_to_terms_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id

    try:
        user_service = await get_user_service()
        await user_service.accept_terms(telegram_id)
        logger.info(f"User {telegram_id} accepted terms")

        await callback.message.edit_text(
            "✅ Спасибо! Вы приняли условия использования."
        )
        await callback.message.answer(
            MAIN_MENU_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Failed to accept terms for user {telegram_id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery):
    await callback.message.edit_text(MAIN_MENU_MESSAGE)
    await callback.message.answer(
        MAIN_MENU_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()