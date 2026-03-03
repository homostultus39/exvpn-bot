from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, LabeledPrice

from bot.database.management.operations.tariffs import get_all_tariffs
from bot.database.management.operations.user import (
    add_days_to_subscription,
    get_user_by_user_id,
    is_trial_used,
    update_user_subscription,
)
from bot.database.management.operations.promo import use_promocode
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last
from bot.database.connection import get_session

from bot.database.management.operations.pending_payment import (
    create_pending_payment,
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
from bot.management.settings import get_settings
import bot.payments.yookassa as yookassa_client

router = Router()
router.message.middleware(AcceptedTermsMiddleware())
router.callback_query.middleware(AcceptedTermsMiddleware())
logger = configure_logger("SUBSCRIPTION_ROUTER", "yellow")
settings = get_settings()


class PromoCodeState(StatesGroup):
    waiting_for_code = State()


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


@router.message(F.text == "🎟 Ввести промокод")
async def enter_promocode_handler(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    await delete_last(message.bot, message.chat.id)

    await state.set_state(PromoCodeState.waiting_for_code)
    sent = await message.answer(
        "🎟 <b>Введите промокод</b>\n\n"
        "Отправьте код одним сообщением.\n"
        "Для отмены нажмите кнопку ниже.",
        reply_markup=get_back_to_menu_keyboard(),
    )
    store(message.chat.id, sent.message_id)


@router.message(PromoCodeState.waiting_for_code)
async def process_promocode_handler(message: Message, state: FSMContext):
    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer("❌ Отправьте промокод текстом.", reply_markup=get_main_menu_keyboard())
        return

    code = raw_text.upper()
    user_id = message.from_user.id
    try:
        await message.delete()
    except Exception:
        pass

    async with get_session() as session:
        user = await get_user_by_user_id(session, user_id)
        if user and user.is_admin:
            await state.clear()
            await message.answer(
                "ℹ️ Администраторам подписка не требуется, промокоды не применяются.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        result = await use_promocode(session, code, user_id)
        if not result:
            await state.clear()
            await message.answer(
                f"❌ Промокод <code>{code}</code> не найден, истёк или исчерпан.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        if result.get("error") == "already_used":
            await state.clear()
            await message.answer(
                f"⚠️ Вы уже использовали промокод <code>{result['code']}</code>.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        days = int(result["days"])
        applied = await add_days_to_subscription(session, user_id, days)

    await state.clear()
    if not applied:
        await message.answer(
            "❌ Не удалось применить промокод. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    await message.answer(
        f"✅ Промокод <code>{result['code']}</code> активирован!\n\n"
        f"🎁 Добавлено <b>{result['days']} дней</b> к подписке.",
        reply_markup=get_main_menu_keyboard(),
    )


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
            f"К сроку подписки добавлено {settings.trial_period_days} дней.\n"
            "Используйте кнопку <b>🔑 Получить ключ</b> для подключения.",
            reply_markup=get_back_to_menu_keyboard()
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
async def back_to_menu_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    chat_id = callback.message.chat.id
    sent_info = await callback.message.answer(CLIENT_INFO)
    sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
    store(chat_id, sent_info.message_id, sent_menu.message_id)
    await callback.answer()