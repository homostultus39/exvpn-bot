from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.user.storage import UserStorage
from bot.entities.user.service import UserService
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.entities.subscription.service import SubscriptionService
from bot.keyboards.user import get_subscription_keyboard
from bot.messages.user import SUBSCRIPTION_REQUIRED
from bot.utils.logger import logger

router = Router()
settings = get_settings()


async def get_services():
    storage = UserStorage(settings.database_path)
    await storage.init_db()

    api_client = get_api_client()
    async with api_client:
        client_repo = ClientRepository(api_client)
        client_service = ClientService(client_repo)
        user_service = UserService(storage, client_service)
        subscription_service = SubscriptionService(client_service)

        return user_service, client_service, subscription_service, api_client


@router.message(F.text == "💎 Подписка")
async def subscription_menu_handler(message: Message):
    await message.answer(
        SUBSCRIPTION_REQUIRED,
        reply_markup=get_subscription_keyboard(is_extension=False)
    )


@router.callback_query(F.data == "extend_subscription")
async def extend_subscription_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 <b>Продление подписки</b>\n\nВыберите тариф:",
        reply_markup=get_subscription_keyboard(is_extension=True)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def buy_subscription_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    tariff_code = callback.data.split("_")[1]

    try:
        user_service, client_service, subscription_service, api_client = await get_services()
        client_id = await user_service.get_client_id(telegram_id)

        await subscription_service.buy_subscription(client_id, tariff_code)

        days = subscription_service.get_tariff_days(tariff_code)

        await callback.message.edit_text(
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"Срок: {days} дней\n\n"
            f"Теперь вы можете получить ключи для подключения."
        )
        await callback.answer("✅ Подписка активирована!")
        logger.info(f"User {telegram_id} bought subscription: {tariff_code}")

    except Exception as e:
        logger.error(f"Error in buy_subscription_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("extend_"))
async def extend_tariff_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    tariff_code = callback.data.split("_")[1]

    try:
        user_service, client_service, subscription_service, api_client = await get_services()
        client_id = await user_service.get_client_id(telegram_id)

        await subscription_service.extend_subscription(client_id, tariff_code)

        days = subscription_service.get_tariff_days(tariff_code)

        await callback.message.edit_text(
            f"✅ <b>Подписка продлена!</b>\n\n"
            f"Добавлено: {days} дней"
        )
        await callback.answer("✅ Подписка продлена!")
        logger.info(f"User {telegram_id} extended subscription: {tariff_code}")

    except Exception as e:
        logger.error(f"Error in extend_tariff_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
