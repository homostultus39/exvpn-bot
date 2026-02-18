from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.entities.tariff.repository import TariffRepository
from bot.entities.tariff.service import TariffService
from bot.entities.subscription.service import SubscriptionService
from bot.keyboards.user import get_subscription_keyboard, get_back_to_menu_keyboard
from bot.messages.user import SUBSCRIPTION_REQUIRED
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last

router = Router()
logger = configure_logger("SUBSCRIPTION_ROUTER", "yellow")


@router.message(F.text == "💎 Подписка")
async def subscription_menu_handler(message: Message):
    await message.delete()
    await delete_last(message.bot, message.chat.id)

    try:
        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            tariffs_response = await tariff_service.get_active_tariffs()

            if not tariffs_response.enabled or not tariffs_response.tariffs:
                sent = await message.answer(
                    "⚠️ <b>Подписки временно недоступны</b>\n\nОбратитесь к администратору.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                store(message.chat.id, sent.message_id)
                return

            sent = await message.answer(
                SUBSCRIPTION_REQUIRED,
                reply_markup=get_subscription_keyboard(tariffs_response.tariffs, is_extension=False)
            )
            store(message.chat.id, sent.message_id)

    except Exception as e:
        logger.error(f"Error in subscription_menu_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "extend_subscription")
async def extend_subscription_handler(callback: CallbackQuery):
    try:
        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            tariffs_response = await tariff_service.get_active_tariffs()

            await callback.message.edit_text(
                "💎 <b>Продление подписки</b>\n\nВыберите тариф:",
                reply_markup=get_subscription_keyboard(tariffs_response.tariffs, is_extension=True)
            )
            await callback.answer()

    except Exception as e:
        logger.error(f"Error in extend_subscription_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("buy_"))
async def buy_subscription_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    tariff_code = callback.data.split("_", 1)[1]

    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            subscription_service = SubscriptionService(client_service, tariff_service)

            client_id = await client_service.get_client_id_by_telegram_id(telegram_id)
            await subscription_service.buy_subscription(client_id, tariff_code)

            tariff = await subscription_service.get_tariff_by_code(tariff_code)
            days = subscription_service.get_tariff_days(tariff) if tariff else "?"

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
    tariff_code = callback.data.split("_", 1)[1]

    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            subscription_service = SubscriptionService(client_service, tariff_service)

            client_id = await client_service.get_client_id_by_telegram_id(telegram_id)
            await subscription_service.extend_subscription(client_id, tariff_code)

            tariff = await subscription_service.get_tariff_by_code(tariff_code)
            days = subscription_service.get_tariff_days(tariff) if tariff else "?"

            await callback.message.edit_text(
                f"✅ <b>Подписка продлена!</b>\n\n"
                f"Добавлено: {days} дней"
            )
            await callback.answer("✅ Подписка продлена!")
            logger.info(f"User {telegram_id} extended subscription: {tariff_code}")

    except Exception as e:
        logger.error(f"Error in extend_tariff_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
