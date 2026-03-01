from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice

from bot.database.management.operations.tariffs import get_all_tariffs
from bot.database.management.operations.user import (
    get_user_by_user_id,
    is_trial_used,
    update_user_subscription,
)
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last
from bot.database.connection import get_session

from bot.database.management.operations.pending_payment import (
    create_pending_payment,
    get_pending_by_order_id,
    get_pending_by_payment_id,
    delete_pending_payment,
)
from bot.keyboards.user import (
    get_main_menu_keyboard,
    get_subscription_keyboard,
    get_payment_method_keyboard,
    get_check_payment_keyboard,
    get_back_to_menu_keyboard,
)
from bot.messages.user import CLIENT_INFO, MAIN_MENU_MESSAGE, SUBSCRIPTION_REQUIRED
from bot.middlewares.terms import AcceptedTermsMiddleware
import bot.payments.rukassa as rukassa_client
import bot.payments.yookassa as yookassa_client

router = Router()
router.message.middleware(AcceptedTermsMiddleware())
router.callback_query.middleware(AcceptedTermsMiddleware())
logger = configure_logger("SUBSCRIPTION_ROUTER", "yellow")


async def _activate_subscription(user_id: int, tariff_code: str) -> None:
    async with get_session() as session:
        await update_user_subscription(session, user_id, tariff_code)


@router.message(F.text == "💎 Подписка")
async def subscription_menu_handler(message: Message):
    await message.delete()
    await delete_last(message.bot, message.chat.id)

    try:
        sent = await message.answer(
            SUBSCRIPTION_REQUIRED,
            reply_markup=await get_subscription_keyboard(is_extension=False)
        )
        store(message.chat.id, sent.message_id)

    except Exception as e:
        logger.error(f"subscription_menu_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs_handler(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            SUBSCRIPTION_REQUIRED,
            reply_markup=await get_subscription_keyboard(is_extension=False)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"back_to_tariffs_handler: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data == "trial")
async def trial_handler(callback: CallbackQuery):
    try:
        async with get_session() as session:
            user = await get_user_by_user_id(session, callback.from_user.id)
            if user and user.is_admin:
                await callback.answer(
                    "ℹ️ Вы администратор. Пробный период не требуется.",
                    show_alert=True,
                )
                return
            if await is_trial_used(session, callback.from_user.id):
                await callback.answer("❌ Вы уже использовали пробный период", show_alert=True)
                return

        await _activate_subscription(callback.from_user.id, "trial")
        await callback.message.edit_text(
            "✅ <b>Пробный период активирован!</b>\n\n"
            "Подписка активна на 3 дня.\n"
            "Используйте кнопку <b>🔑 Получить ключ</b> для подключения."
        )
        await callback.answer("Пробный период активирован")

    except Exception as e:
        logger.error(f"trial_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "extend_subscription")
async def extend_subscription_handler(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "💎 <b>Продление подписки</b>\n\nВыберите тариф:",
            reply_markup=await get_subscription_keyboard(is_extension=True)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"extend_subscription_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("buy_"))
async def buy_select_payment(callback: CallbackQuery):
    tariff_code = callback.data.split("_", 1)[1]
    await _show_payment_methods(callback, tariff_code, is_extension=False)


@router.callback_query(F.data.regexp(r"^extend_(?!subscription$).+"))
async def extend_select_payment(callback: CallbackQuery):
    tariff_code = callback.data.split("_", 1)[1]
    await _show_payment_methods(callback, tariff_code, is_extension=True)


async def _show_payment_methods(callback: CallbackQuery, tariff_code: str, is_extension: bool):
    try:
        async with get_session() as session:
            user = await get_user_by_user_id(session, callback.from_user.id)
            if user and user.is_admin:
                await callback.answer(
                    "ℹ️ Вы администратор. Подписка не требуется.",
                    show_alert=True,
                )
                return

            tariffs = await get_all_tariffs(session)

        tariff = next((t for t in tariffs if t.code == tariff_code), None)
        if not tariff:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            return

        action = "Продление" if is_extension else "Покупка"
        await callback.message.edit_text(
            f"💳 <b>{action} подписки</b>\n\n"
            f"📦 Тариф: <b>{tariff.name}</b> ({tariff.days} дней)\n\n"
            f"Выберите способ оплаты:",
            reply_markup=get_payment_method_keyboard(
                tariff_code, tariff.price_rub, tariff.price_stars, is_extension
            )
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"_show_payment_methods: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    # pay_stars_{tariff_code}_{prefix}
    # prefix занимает последний сегмент: "buy" или "extend"
    prefix = parts[-1]
    tariff_code = "_".join(parts[2:-1])
    is_extension = prefix == "extend"

    try:
        async with get_session() as session:
            tariffs = await get_all_tariffs(session)

        tariff = next((t for t in tariffs if t.code == tariff_code), None)
        if not tariff:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            return

        action = "extend" if is_extension else "buy"
        payload = f"stars_{tariff_code}_{action}_{callback.from_user.id}"

        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"ExVPN — {tariff.name}",
            description=f"Подписка на {tariff.days} дней",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=tariff.name, amount=tariff.price_stars)],
            need_name=False,
            need_phone_number=False,
            need_shipping_address=False,
            is_flexible=False,
        )
        await callback.answer("⭐ Счёт выставлен")

    except Exception as e:
        logger.error(f"pay_stars_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query):
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    logger.info(f"Stars payment success: {user_id} payload={payload}")

    try:
        # payload format: stars_{tariff_code}_{action}_{user_id}
        parts = payload.split("_")
        action = parts[-2]
        tariff_code = "_".join(parts[1:-2])
        is_extension = action == "extend"

        await _activate_subscription(user_id, tariff_code)

        verb = "продлена" if is_extension else "активирована"
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Подписка {verb}.\n"
            f"Используйте кнопку <b>🔑 Получить ключ</b> для подключения.",
            reply_markup=get_main_menu_keyboard(),
        )
        logger.info(f"Stars subscription activated: user={user_id} tariff={tariff_code}")

    except Exception as e:
        logger.error(f"successful_payment_handler: {e}")
        await message.answer("❌ Ошибка активации подписки. Обратитесь в поддержку.")


@router.callback_query(F.data.startswith("pay_rukassa_"))
async def pay_rukassa_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    prefix = parts[-1]
    tariff_code = "_".join(parts[2:-1])
    is_extension = prefix == "extend"

    try:
        async with get_session() as session:
            tariffs = await get_all_tariffs(session)

        tariff = next((t for t in tariffs if t.code == tariff_code), None)
        if not tariff:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            return

        result = await rukassa_client.create_payment(
            telegram_id=callback.from_user.id,
            amount=tariff.price_rub,
            tariff_code=tariff_code,
            is_extension=is_extension,
        )

        if not result["success"]:
            await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
            return

        order_id = result["order_id"]

        async with get_session() as session:
            await create_pending_payment(
                session=session,
                telegram_id=callback.from_user.id,
                tariff_code=tariff_code,
                is_extension=is_extension,
                payment_method="rukassa",
                amount=tariff.price_rub,
                order_id=order_id,
            )

        await callback.message.edit_text(
            f"🔵 <b>Оплата через Rukassa</b>\n\n"
            f"📦 Тариф: <b>{tariff.name}</b> ({tariff.days} дней)\n"
            f"💰 Сумма: <b>{tariff.price_rub} ₽</b>\n\n"
            f'<a href="{result["url"]}">👉 Перейти к оплате</a>\n\n'
            f"После оплаты нажмите кнопку ниже:",
            reply_markup=get_check_payment_keyboard("ruk", order_id),
            disable_web_page_preview=True,
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"pay_rukassa_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("check_ruk_"))
async def check_rukassa_handler(callback: CallbackQuery):
    order_id = callback.data.removeprefix("check_ruk_")
    await callback.answer("⏳ Проверяем...", show_alert=False)

    try:
        result = await rukassa_client.check_payment(order_id)

        if result["status"] == "PAID":
            async with get_session() as session:
                pending = await get_pending_by_order_id(session, order_id)
                if not pending:
                    await callback.answer("❌ Платёж не найден", show_alert=True)
                    return

                user_id = pending.user_id
                tariff_code = pending.tariff_code
                is_extension = pending.is_extension
                record_id = pending.id

            await _activate_subscription(user_id, tariff_code)

            async with get_session() as session:
                await delete_pending_payment(session, record_id)

            verb = "продлена" if is_extension else "активирована"
            await callback.message.edit_text(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"Подписка {verb}.\n"
                f"Используйте кнопку <b>🔑 Получить ключ</b> для подключения.",
                reply_markup=get_back_to_menu_keyboard(),
            )
            logger.info(f"Rukassa payment confirmed: order={order_id}")

        elif result["status"] in ("WAITING", "PENDING", ""):
            await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)
        else:
            await callback.answer("❌ Платёж не найден или отменён.", show_alert=True)

    except Exception as e:
        logger.error(f"check_rukassa_handler: {e}")
        await callback.answer("❌ Ошибка проверки платежа.", show_alert=True)


@router.callback_query(F.data.startswith("pay_yookassa_"))
async def pay_yookassa_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    prefix = parts[-1]
    tariff_code = "_".join(parts[2:-1])
    is_extension = prefix == "extend"

    try:
        async with get_session() as session:
            tariffs = await get_all_tariffs(session)

        tariff = next((t for t in tariffs if t.code == tariff_code), None)
        if not tariff:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            return

        result = await yookassa_client.create_payment(
            telegram_id=callback.from_user.id,
            amount=tariff.price_rub,
            tariff_code=tariff_code,
            tariff_name=tariff.name,
            is_extension=is_extension,
            return_url=f"https://t.me/{(await callback.bot.get_me()).username}",
        )

        if not result["success"]:
            await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
            return

        async with get_session() as session:
            await create_pending_payment(
                session=session,
                telegram_id=callback.from_user.id,
                tariff_code=tariff_code,
                is_extension=is_extension,
                payment_method="yookassa",
                amount=tariff.price_rub,
                payment_id=result["payment_id"],
                order_id=result["order_id"],
            )

        await callback.message.edit_text(
            f"💳 <b>Оплата через YooMoney</b>\n\n"
            f"📦 Тариф: <b>{tariff.name}</b> ({tariff.days} дней)\n"
            f"💰 Сумма: <b>{tariff.price_rub} ₽</b>\n\n"
            f'<a href="{result["url"]}">👉 Перейти к оплате</a>\n\n'
            f"После оплаты нажмите кнопку ниже:",
            reply_markup=get_check_payment_keyboard("yookassa", result["payment_id"]),
            disable_web_page_preview=True,
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"pay_yookassa_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("check_yookassa_"))
async def check_yookassa_handler(callback: CallbackQuery):
    payment_id = callback.data.removeprefix("check_yookassa_")
    await callback.answer("⏳ Проверяем...", show_alert=False)

    try:
        result = await yookassa_client.check_payment(payment_id)

        if result["status"] == "PAID":
            async with get_session() as session:
                pending = await get_pending_by_payment_id(session, payment_id)
                if not pending:
                    await callback.answer("❌ Платёж не найден", show_alert=True)
                    return

                user_id = pending.user_id
                tariff_code = pending.tariff_code
                is_extension = pending.is_extension
                record_id = pending.id

            await _activate_subscription(user_id, tariff_code)

            async with get_session() as session:
                await delete_pending_payment(session, record_id)

            verb = "продлена" if is_extension else "активирована"
            await callback.message.edit_text(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"Подписка {verb}.\n"
                f"Используйте кнопку <b>🔑 Получить ключ</b> для подключения.",
                reply_markup=get_back_to_menu_keyboard(),
            )
            logger.info(f"YooMoney payment confirmed: payment_id={payment_id}")

        elif result["status"] == "PENDING":
            await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)
        else:
            await callback.answer("❌ Платёж не найден или отменён.", show_alert=True)

    except Exception as e:
        logger.error(f"check_yookassa_handler: {e}")
        await callback.answer("❌ Ошибка проверки платежа.", show_alert=True)


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_handler(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            SUBSCRIPTION_REQUIRED,
            reply_markup=await get_subscription_keyboard(is_extension=False)
        )
        await callback.answer("Платёж отменён")
    except Exception as e:
        logger.error(f"cancel_payment_handler: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery):
    await callback.message.delete()
    chat_id = callback.message.chat.id
    sent_info = await callback.message.answer(CLIENT_INFO)
    sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
    store(chat_id, sent_info.message_id, sent_menu.message_id)
    await callback.answer()