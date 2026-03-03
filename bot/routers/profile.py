from datetime import datetime

import pytz
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.database.connection import get_session
from bot.database.management.operations.cluster import get_cluster_by_id
from bot.database.management.operations.peer import get_peers_by_user
from bot.database.management.operations.user import get_user_by_user_id
from bot.database.management.operations.user import get_referral_stats
from bot.keyboards.user import get_back_to_menu_keyboard, get_main_menu_keyboard, get_profile_keyboard
from bot.management.settings import get_settings
from bot.messages.user import (
    CLIENT_INFO,
    MAIN_MENU_MESSAGE,
    PROFILE_MESSAGE_TEMPLATE,
    SUBSCRIPTION_ACTIVE_TEMPLATE,
    SUBSCRIPTION_EXPIRED,
    REFERRAL_TEMPLATE,
)
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last, clear

router = Router()
logger = configure_logger("PROFILE_ROUTER", "magenta")
settings = get_settings()
tz = pytz.timezone(settings.timezone)


@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message):
    telegram_id = message.from_user.id
    username = message.from_user.username or f"user_{telegram_id}"

    await message.delete()
    await delete_last(message.bot, message.chat.id)

    try:
        async with get_session() as session:
            user = await get_user_by_user_id(session, telegram_id)
            if user is None:
                await message.answer("❌ Вы не зарегистрированы. Используйте /start")
                return
            expires_at = user.expires_at
            if expires_at is None:
                subscription_status = "♾️ Без ограничений (администратор)"
            elif expires_at > datetime.now(tz):
                local_expires_at = expires_at.astimezone(tz)
                subscription_status = SUBSCRIPTION_ACTIVE_TEMPLATE.format(
                    expires_at=local_expires_at.strftime("%d.%m.%Y %H:%M")
                )
            else:
                subscription_status = SUBSCRIPTION_EXPIRED

            peers = await get_peers_by_user(session, user.id)

            profile_text = PROFILE_MESSAGE_TEMPLATE.format(
                telegram_id=telegram_id,
                username=username,
                subscription_status=subscription_status,
                peers_count=len(peers)
            )

            sent = await message.answer(
                profile_text,
                reply_markup=get_profile_keyboard()
            )
            store(message.chat.id, sent.message_id)

    except Exception as e:
        logger.error(f"Error in profile_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "my_keys")
async def my_keys_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id

    await callback.message.delete()
    clear(callback.message.chat.id)

    try:
        async with get_session() as session:
            user = await get_user_by_user_id(session, telegram_id)
            if user is None:
                await callback.message.answer("❌ Вы не зарегистрированы. Используйте /start")
                await callback.answer()
                return
            peers = await get_peers_by_user(session, user.id)

            if not peers:
                await callback.message.answer(
                    "🔑 <b>Мои ключи</b>\n\n"
                    "У вас пока нет активных ключей.\n"
                    "Используйте 🔑 Получить ключ для создания.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                await callback.answer()
                return

            await callback.answer()

            for peer in peers:
                cluster = await get_cluster_by_id(session, peer.cluster_id)
                cluster_name = cluster.public_name if cluster else "Неизвестно"
                key_type_label = "Белый список" if peer.key_type == "whitelist" else "VPN"
                region_label = (peer.region_code or "—").upper()
                cluster_role = " (шлюз white-list)" if cluster and cluster.is_whitelist_gateway else ""
                await callback.message.answer(
                    f"🌍 {cluster_name}{cluster_role} ({region_label})\n"
                    f"🧭 Тип: {key_type_label}\n"
                    f"🔑 <code>{peer.url}</code>"
                )

            sent_info = await callback.message.answer(CLIENT_INFO)
            sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
            store(callback.message.chat.id, sent_info.message_id, sent_menu.message_id)

    except Exception as e:
        logger.error(f"Error in my_keys_handler: {e}")
        await callback.message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "referral")
async def referral_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    try:
        async with get_session() as session:
            user = await get_user_by_user_id(session, telegram_id)
            if user is None:
                await callback.answer("❌ Вы не зарегистрированы. Используйте /start", show_alert=True)
                return
            invited_count, paid_count, bonus_days = await get_referral_stats(session, telegram_id)

        bot_username = (await callback.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{telegram_id}"
        await callback.message.edit_text(
            REFERRAL_TEMPLATE.format(
                ref_link=ref_link,
                invited_count=invited_count,
                paid_count=paid_count,
                bonus_days=bonus_days,
                referral_bonus_days=settings.referral_bonus_days,
            ),
            reply_markup=get_back_to_menu_keyboard(),
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in referral_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
