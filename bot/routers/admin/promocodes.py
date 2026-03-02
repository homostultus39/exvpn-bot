from datetime import datetime

import pytz
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.database.connection import get_session
from bot.database.management.operations.promo import (
    create_promocode,
    delete_promocode,
    get_promocode_by_code,
    list_promocodes,
)
from bot.keyboards.admin import get_admin_menu_keyboard
from bot.management.logger import configure_logger
from bot.management.settings import get_settings
from bot.middlewares.admin import AdminMiddleware
from bot.middlewares.fsm_cancel import cancel_active_fsm

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_PROMOCODES", "red")
tz = pytz.timezone(get_settings().timezone)

PREFIX = "promo"


class PromoStates(StatesGroup):
    create_code = State()
    create_days = State()
    create_uses = State()
    create_expiry = State()
    delete_code = State()


def _promo_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo_create")],
        [InlineKeyboardButton(text="🗑 Удалить промокод", callback_data="admin_promo_delete")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_promo_list")],
    ])


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{PREFIX}_cancel")]
    ])


async def _edit_prompt(bot: Bot, data: dict, text: str, keyboard: InlineKeyboardMarkup | None) -> None:
    try:
        await bot.edit_message_text(
            chat_id=data["prompt_chat_id"],
            message_id=data["prompt_msg_id"],
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        pass


@router.message(F.text == "🎟 Промокоды")
async def admin_promocodes_menu(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    await message.answer(
        "🎟 <b>Управление промокодами</b>\n\nВыберите действие:",
        reply_markup=_promo_menu_keyboard(),
    )


@router.callback_query(StateFilter(PromoStates), F.data == f"{PREFIX}_cancel")
async def cancel_promo_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Операция отменена.", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_promo_create")
async def promo_create_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎟 <b>Создание промокода</b>\n\nШаг 1/4: Введите код промокода (например: EXVPN30):",
        reply_markup=_cancel_keyboard(),
    )
    await state.update_data(
        prompt_msg_id=callback.message.message_id,
        prompt_chat_id=callback.message.chat.id,
    )
    await state.set_state(PromoStates.create_code)
    await callback.answer()


@router.message(PromoStates.create_code)
async def promo_create_code(message: Message, state: FSMContext, bot: Bot):
    code = message.text.strip().upper()
    await message.delete()
    data = await state.get_data()

    if len(code) < 3:
        await _edit_prompt(
            bot,
            data,
            "🎟 <b>Создание промокода</b>\n\nШаг 1/4: Введите код промокода:\n\n"
            "❌ Код слишком короткий (минимум 3 символа).",
            _cancel_keyboard(),
        )
        return

    async with get_session() as session:
        existing = await get_promocode_by_code(session, code)
    if existing:
        await _edit_prompt(
            bot,
            data,
            f"🎟 <b>Создание промокода</b>\n\nШаг 1/4: Введите код промокода:\n\n"
            f"❌ Промокод <code>{code}</code> уже существует.",
            _cancel_keyboard(),
        )
        return

    await state.update_data(code=code)
    await _edit_prompt(
        bot,
        data,
        "🎟 <b>Создание промокода</b>\n\nШаг 2/4: Введите количество дней (целое число):",
        _cancel_keyboard(),
    )
    await state.set_state(PromoStates.create_days)


@router.message(PromoStates.create_days)
async def promo_create_days(message: Message, state: FSMContext, bot: Bot):
    await message.delete()
    data = await state.get_data()
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await _edit_prompt(
            bot,
            data,
            "🎟 <b>Создание промокода</b>\n\nШаг 2/4: Введите количество дней:\n\n"
            "❌ Введите положительное целое число.",
            _cancel_keyboard(),
        )
        return

    await state.update_data(days=days)
    await _edit_prompt(
        bot,
        data,
        "🎟 <b>Создание промокода</b>\n\n"
        "Шаг 3/4: Введите лимит использований.\n"
        "0 = без лимита:",
        _cancel_keyboard(),
    )
    await state.set_state(PromoStates.create_uses)


@router.message(PromoStates.create_uses)
async def promo_create_uses(message: Message, state: FSMContext, bot: Bot):
    await message.delete()
    data = await state.get_data()
    try:
        max_uses = int(message.text.strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await _edit_prompt(
            bot,
            data,
            "🎟 <b>Создание промокода</b>\n\nШаг 3/4: Введите лимит использований:\n\n"
            "❌ Введите целое число 0 или больше.",
            _cancel_keyboard(),
        )
        return

    await state.update_data(max_uses=max_uses)
    await _edit_prompt(
        bot,
        data,
        "🎟 <b>Создание промокода</b>\n\n"
        "Шаг 4/4: Введите дату истечения в формате ДД.ММ.ГГГГ\n"
        "или отправьте <code>-</code> чтобы не задавать срок.",
        _cancel_keyboard(),
    )
    await state.set_state(PromoStates.create_expiry)


@router.message(PromoStates.create_expiry)
async def promo_create_expiry(message: Message, state: FSMContext, bot: Bot):
    await message.delete()
    data = await state.get_data()
    raw = message.text.strip()

    expires_at = None
    if raw != "-":
        try:
            expires_at = tz.localize(datetime.strptime(raw, "%d.%m.%Y"))
        except ValueError:
            await _edit_prompt(
                bot,
                data,
                "🎟 <b>Создание промокода</b>\n\nШаг 4/4: Введите дату истечения:\n\n"
                "❌ Неверный формат. Используйте ДД.ММ.ГГГГ или <code>-</code>.",
                _cancel_keyboard(),
            )
            return

    async with get_session() as session:
        promo = await create_promocode(
            session=session,
            code=data["code"],
            days=data["days"],
            max_uses=data["max_uses"],
            expires_at=expires_at,
        )

    await state.clear()
    await _edit_prompt(
        bot,
        data,
        "✅ <b>Промокод создан</b>\n\n"
        f"Код: <code>{promo.code}</code>\n"
        f"Дней: <b>{promo.days}</b>\n"
        f"Лимит: <b>{'без лимита' if promo.max_uses == 0 else promo.max_uses}</b>\n"
        f"Истекает: <b>{promo.expires_at.strftime('%d.%m.%Y') if promo.expires_at else 'никогда'}</b>",
        None,
    )
    await message.answer("🔐 Вы в главном меню.", reply_markup=get_admin_menu_keyboard())
    logger.info(f"Promo {promo.code} created by admin {message.from_user.id}")


@router.callback_query(F.data == "admin_promo_delete")
async def promo_delete_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🗑 <b>Удаление промокода</b>\n\nВведите код промокода:",
        reply_markup=_cancel_keyboard(),
    )
    await state.update_data(
        prompt_msg_id=callback.message.message_id,
        prompt_chat_id=callback.message.chat.id,
    )
    await state.set_state(PromoStates.delete_code)
    await callback.answer()


@router.message(PromoStates.delete_code)
async def promo_delete_code(message: Message, state: FSMContext, bot: Bot):
    code = message.text.strip().upper()
    await message.delete()
    data = await state.get_data()

    async with get_session() as session:
        deleted = await delete_promocode(session, code)

    await state.clear()
    if deleted:
        text = f"✅ Промокод <code>{code}</code> удалён."
        logger.info(f"Promo {code} deleted by admin {message.from_user.id}")
    else:
        text = f"❌ Промокод <code>{code}</code> не найден."
    await _edit_prompt(bot, data, text, None)
    await message.answer("🔐 Вы в главном меню.", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_promo_list")
async def promo_list_handler(callback: CallbackQuery):
    async with get_session() as session:
        promos = await list_promocodes(session)

    if not promos:
        await callback.answer("Промокодов пока нет", show_alert=True)
        return

    lines = ["🎟 <b>Список промокодов</b>\n"]
    for promo in promos:
        limit = "∞" if promo.max_uses == 0 else str(promo.max_uses)
        expiry = promo.expires_at.strftime("%d.%m.%Y") if promo.expires_at else "∞"
        lines.append(
            f"<code>{promo.code}</code> — {promo.days} дн.\n"
            f"Использовано: <b>{promo.used_count}/{limit}</b>\n"
            f"Истекает: <b>{expiry}</b>\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=_promo_menu_keyboard(),
    )
    await callback.answer()
