from datetime import datetime

import pytz
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.database.connection import get_session
from bot.database.management.operations.user import (
    get_user_by_user_id,
    register_user_by_admin,
)
from bot.keyboards.admin import (
    get_admin_menu_keyboard,
    get_client_register_expiration_date_keyboard,
    get_client_register_is_admin_keyboard,
    get_clients_keyboard,
    get_fsm_keyboard,
)
from bot.management.logger import configure_logger
from bot.management.settings import get_settings
from bot.middlewares.admin import AdminMiddleware
from bot.middlewares.fsm_cancel import cancel_active_fsm

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_CLIENTS", "red")

PREFIX = "cr"
TIMEZONE = pytz.timezone(get_settings().timezone)


class ClientRegisterForm(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_expiration_date = State()
    waiting_for_is_admin = State()


def _format_datetime(value: datetime) -> str:
    return value.astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M")


async def _edit_prompt(bot: Bot, data: dict, text: str, keyboard) -> None:
    try:
        await bot.edit_message_text(
            chat_id=data["prompt_chat_id"],
            message_id=data["prompt_msg_id"],
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        pass


async def _delete_prompt(bot: Bot, data: dict) -> None:
    try:
        await bot.delete_message(data["prompt_chat_id"], data["prompt_msg_id"])
    except Exception:
        pass


@router.message(F.text == "👥 Клиенты")
async def clients_menu_handler(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    await message.answer(
        "👥 <b>Управление клиентами</b>\n\n"
        "Выберите действие:",
        reply_markup=get_clients_keyboard(),
    )


@router.callback_query(F.data == "admin_clients_refresh")
async def clients_refresh_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "👥 <b>Управление клиентами</b>\n\n"
        "Выберите действие:",
        reply_markup=get_clients_keyboard(),
    )
    await callback.answer("Обновлено")


@router.callback_query(StateFilter(ClientRegisterForm), F.data == f"{PREFIX}_cancel")
async def cancel_client_register(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Регистрация клиента отменена.", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_register_client")
async def start_client_register(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    await callback.message.delete()
    prompt = await callback.message.answer(
        "👤 <b>Регистрация клиента</b>\n\n"
        "Шаг 1/3: Введите Telegram ID пользователя\n"
        "(Например: 123456789)",
        reply_markup=get_fsm_keyboard(PREFIX, back=False),
    )
    await state.update_data(prompt_msg_id=prompt.message_id, prompt_chat_id=prompt.chat.id)
    await state.set_state(ClientRegisterForm.waiting_for_user_id)
    await callback.answer()


@router.message(ClientRegisterForm.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext, bot: Bot):
    await message.delete()
    data = await state.get_data()
    try:
        user_id = int(message.text.strip())
        if user_id <= 0:
            raise ValueError

        async with get_session() as session:
            existing_user = await get_user_by_user_id(session, user_id)

        if existing_user:
            expires_info = "не ограничена" if existing_user.expires_at is None else _format_datetime(existing_user.expires_at)
            await _delete_prompt(bot, data)
            await message.answer(
                "⚠️ <b>Пользователь уже существует</b>\n\n"
                f"👤 Telegram ID: <code>{existing_user.user_id}</code>\n"
                f"📅 Подписка до: {expires_info}\n"
                f"🔐 Администратор: {'✅ Да' if existing_user.is_admin else '❌ Нет'}\n"
                f"📦 Статус: <code>{existing_user.subscription_status}</code>\n\n"
                "Регистрация отменена.",
                reply_markup=get_admin_menu_keyboard(),
            )
            await state.clear()
            return

        await state.update_data(user_id=user_id)
        await _edit_prompt(
            bot,
            data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 2/3: Введите дату истечения подписки\n"
            "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "(Например: 31.12.2026 или 31.12.2026 23:59)\n\n"
            "💡 Для администраторов можно пропустить этот шаг",
            get_client_register_expiration_date_keyboard(PREFIX),
        )
        await state.set_state(ClientRegisterForm.waiting_for_expiration_date)
    except ValueError:
        await _edit_prompt(
            bot,
            data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 1/3: Введите Telegram ID пользователя\n"
            "(Например: 123456789)\n\n"
            "❌ Некорректный ID. Введите положительное число:",
            get_fsm_keyboard(PREFIX, back=False),
        )


@router.callback_query(ClientRegisterForm.waiting_for_expiration_date, F.data == f"{PREFIX}_back")
async def cr_back_to_user_id(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "👤 <b>Регистрация клиента</b>\n\n"
        "Шаг 1/3: Введите Telegram ID пользователя:",
        reply_markup=get_fsm_keyboard(PREFIX, back=False),
    )
    await state.set_state(ClientRegisterForm.waiting_for_user_id)
    await callback.answer()


@router.callback_query(ClientRegisterForm.waiting_for_expiration_date, F.data == f"{PREFIX}_skip_expiration")
async def skip_expiration_date(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.update_data(expires_at=None)
    await _edit_prompt(
        bot,
        data,
        "👤 <b>Регистрация клиента</b>\n\n"
        "Шаг 3/3: Является ли пользователь администратором?",
        get_client_register_is_admin_keyboard(PREFIX),
    )
    await state.set_state(ClientRegisterForm.waiting_for_is_admin)
    await callback.answer()


@router.message(ClientRegisterForm.waiting_for_expiration_date)
async def process_expiration_date(message: Message, state: FSMContext, bot: Bot):
    await message.delete()
    data = await state.get_data()
    try:
        raw_value = message.text.strip()
        try:
            parsed = datetime.strptime(raw_value, "%d.%m.%Y %H:%M")
        except ValueError:
            parsed = datetime.strptime(raw_value, "%d.%m.%Y")

        expires_at = TIMEZONE.localize(parsed)
        if expires_at <= datetime.now(TIMEZONE):
            await _edit_prompt(
                bot,
                data,
                "👤 <b>Регистрация клиента</b>\n\n"
                "Шаг 2/3: Введите дату истечения подписки\n"
                "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
                "⚠️ Указанная дата уже прошла. Введите будущую дату:",
                get_client_register_expiration_date_keyboard(PREFIX),
            )
            return

        await state.update_data(expires_at=expires_at.isoformat())
        await _edit_prompt(
            bot,
            data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 3/3: Является ли пользователь администратором?",
            get_client_register_is_admin_keyboard(PREFIX),
        )
        await state.set_state(ClientRegisterForm.waiting_for_is_admin)
    except ValueError:
        await _edit_prompt(
            bot,
            data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 2/3: Введите дату истечения подписки\n"
            "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
            "❌ Некорректный формат. Примеры: 31.12.2026 или 31.12.2026 23:59\n"
            "Попробуйте ещё раз:",
            get_client_register_expiration_date_keyboard(PREFIX),
        )


@router.callback_query(ClientRegisterForm.waiting_for_is_admin, F.data == f"{PREFIX}_back")
async def cr_back_to_expiration(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await _edit_prompt(
        bot,
        data,
        "👤 <b>Регистрация клиента</b>\n\n"
        "Шаг 2/3: Введите дату истечения подписки\n"
        "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
        "💡 Для администраторов можно пропустить этот шаг",
        get_client_register_expiration_date_keyboard(PREFIX),
    )
    await state.set_state(ClientRegisterForm.waiting_for_expiration_date)
    await callback.answer()


@router.callback_query(
    ClientRegisterForm.waiting_for_is_admin,
    F.data.in_({f"{PREFIX}_is_admin_yes", f"{PREFIX}_is_admin_no"}),
)
async def process_is_admin(callback: CallbackQuery, state: FSMContext, bot: Bot):
    is_admin = callback.data == f"{PREFIX}_is_admin_yes"
    data = await state.get_data()
    user_id = data["user_id"]
    expires_at_raw = data.get("expires_at")
    expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else None

    if not is_admin and expires_at is None:
        await _delete_prompt(bot, data)
        await callback.message.answer(
            "❌ <b>Ошибка регистрации</b>\n\n"
            "Для обычных пользователей необходимо указать дату истечения подписки.\n"
            "Пожалуйста, начните регистрацию заново.",
            reply_markup=get_admin_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return

    try:
        async with get_session() as session:
            user = await register_user_by_admin(
                session=session,
                user_id=user_id,
                is_admin=is_admin,
                expires_at=expires_at,
            )

        await _delete_prompt(bot, data)
        expires_info = (
            "без ограничений (администратор)"
            if user.expires_at is None
            else _format_datetime(user.expires_at)
        )
        await callback.message.answer(
            "✅ <b>Клиент зарегистрирован!</b>\n\n"
            f"👤 Telegram ID: <code>{user.user_id}</code>\n"
            f"🆔 Client ID: <code>{user.id}</code>\n"
            f"📅 Подписка до: {expires_info}\n"
            f"🔐 Администратор: {'✅ Да' if user.is_admin else '❌ Нет'}\n\n"
            "Пользователь может начать использовать бота!",
            reply_markup=get_admin_menu_keyboard(),
        )
        logger.info(
            f"Admin {callback.from_user.id} registered user {user.user_id}, "
            f"expires={user.expires_at}, is_admin={user.is_admin}"
        )
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error registering client: {e}")
        await _delete_prompt(bot, data)
        await callback.message.answer(
            "❌ Ошибка при регистрации клиента.\n\n"
            "Проверьте данные и попробуйте снова через /admin",
            reply_markup=get_admin_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
