from datetime import datetime
from bot.management.timezone import get_timezone, now as get_now
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from bot.management.dependencies import get_api_client
from bot.management.fsm_utils import cancel_active_fsm
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import get_admin_menu_keyboard, get_fsm_keyboard
from bot.management.logger import configure_logger

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_CLIENT_REGISTER", "red")

PREFIX = "cr"


class ClientRegisterForm(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_expiration_date = State()


async def _edit_prompt(bot: Bot, data: dict, text: str, keyboard) -> None:
    try:
        await bot.edit_message_text(
            chat_id=data["prompt_chat_id"],
            message_id=data["prompt_msg_id"],
            text=text,
            reply_markup=keyboard
        )
    except Exception:
        pass


async def _delete_prompt(bot: Bot, data: dict) -> None:
    try:
        await bot.delete_message(data["prompt_chat_id"], data["prompt_msg_id"])
    except Exception:
        pass


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
    msg = await callback.message.answer(
        "👤 <b>Регистрация клиента</b>\n\n"
        "Шаг 1/2: Введите Telegram ID пользователя\n"
        "(Например: 123456789)",
        reply_markup=get_fsm_keyboard(PREFIX, back=False)
    )
    await state.update_data(prompt_msg_id=msg.message_id, prompt_chat_id=msg.chat.id)
    await state.set_state(ClientRegisterForm.waiting_for_user_id)
    await callback.answer()


@router.message(ClientRegisterForm.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext, bot: Bot):
    text = message.text
    await message.delete()
    data = await state.get_data()

    try:
        user_id = int(text.strip())
        if user_id <= 0:
            raise ValueError("User ID must be positive")

        await state.update_data(user_id=user_id)
        await _edit_prompt(
            bot, data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 2/2: Введите дату истечения подписки\n"
            "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "(Например: 31.12.2026 или 31.12.2026 23:59)",
            get_fsm_keyboard(PREFIX, back=True)
        )
        await state.set_state(ClientRegisterForm.waiting_for_expiration_date)
    except ValueError:
        await _edit_prompt(
            bot, data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 1/2: Введите Telegram ID пользователя\n"
            "(Например: 123456789)\n\n"
            "❌ Некорректный ID. Введите положительное число:",
            get_fsm_keyboard(PREFIX, back=False)
        )


@router.callback_query(ClientRegisterForm.waiting_for_expiration_date, F.data == f"{PREFIX}_back")
async def cr_back_to_user_id(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "👤 <b>Регистрация клиента</b>\n\n"
        "Шаг 1/2: Введите Telegram ID пользователя:",
        reply_markup=get_fsm_keyboard(PREFIX, back=False)
    )
    await state.set_state(ClientRegisterForm.waiting_for_user_id)
    await callback.answer()


@router.message(ClientRegisterForm.waiting_for_expiration_date)
async def process_expiration_date(message: Message, state: FSMContext, bot: Bot):
    date_str = message.text.strip()
    await message.delete()
    data = await state.get_data()

    try:
        try:
            expires_at = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
        except ValueError:
            expires_at = datetime.strptime(date_str, "%d.%m.%Y")

        if expires_at < get_now():
            await _edit_prompt(
                bot, data,
                "👤 <b>Регистрация клиента</b>\n\n"
                "Шаг 2/2: Введите дату истечения подписки\n"
                "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
                "⚠️ Указанная дата уже прошла. Введите будущую дату:",
                get_fsm_keyboard(PREFIX, back=True)
            )
            return

        user_id = data["user_id"]

        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)
            username = str(user_id)

            existing_client = await client_service.find_by_username(username)
            if existing_client:
                local_expires = existing_client.expires_at.astimezone(get_timezone())
                await _delete_prompt(bot, data)
                await message.answer(
                    f"⚠️ <b>Клиент уже существует</b>\n\n"
                    f"🆔 ID: <code>{existing_client.id}</code>\n"
                    f"👤 Username: {existing_client.username}\n"
                    f"📅 Текущая дата истечения: {local_expires.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Регистрация отменена.",
                    reply_markup=get_admin_menu_keyboard()
                )
                await state.clear()
                return

            client = await client_service.create_client(username, expires_at)
            local_expires = client.expires_at.astimezone(get_timezone())

        await _delete_prompt(bot, data)
        await message.answer(
            f"✅ <b>Клиент зарегистрирован!</b>\n\n"
            f"👤 Telegram ID: <code>{user_id}</code>\n"
            f"🆔 Client ID: <code>{client.id}</code>\n"
            f"📅 Подписка до: {local_expires.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Пользователь может начать использовать бота!",
            reply_markup=get_admin_menu_keyboard()
        )
        logger.info(f"Admin {message.from_user.id} registered client {client.id} for user {user_id} until {expires_at}")
        await state.clear()

    except ValueError:
        await _edit_prompt(
            bot, data,
            "👤 <b>Регистрация клиента</b>\n\n"
            "Шаг 2/2: Введите дату истечения подписки\n"
            "Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
            "❌ Некорректный формат. Примеры: 31.12.2026 или 31.12.2026 23:59\n"
            "Попробуйте ещё раз:",
            get_fsm_keyboard(PREFIX, back=True)
        )
    except Exception as e:
        logger.error(f"Error registering client: {e}")
        await _delete_prompt(bot, data)
        await message.answer(
            f"❌ Ошибка при регистрации клиента:\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"Проверьте данные и попробуйте снова через /admin",
            reply_markup=get_admin_menu_keyboard()
        )
        await state.clear()
