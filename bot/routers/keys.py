from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from uuid import UUID

from bot.core.xray_panel_client import XrayPanelClient
from bot.database.connection import get_session
from bot.database.management.operations.cluster import (
    get_standard_clusters,
    get_cluster_by_id,
    get_whitelist_cluster,
)
from bot.database.management.operations.peer import get_or_create_peer_for_cluster
from bot.database.management.operations.user import (
    get_user_by_user_id,
    is_subscription_active,
)
from bot.keyboards.user import (
    get_back_to_menu_keyboard,
    get_key_mode_keyboard,
    get_locations_keyboard,
    get_main_menu_keyboard,
)
from bot.management.logger import configure_logger
from bot.management.message_tracker import clear, delete_last, store
from bot.messages.user import (
    CLIENT_INFO,
    KEY_RECEIVED_TEMPLATE,
    MAIN_MENU_MESSAGE,
    SELECT_KEY_MODE,
    SELECT_LOCATION,
)

router = Router()
logger = configure_logger("KEYS_ROUTER", "cyan")


async def _issue_standard_key(callback: CallbackQuery, cluster_id: UUID) -> None:
    telegram_id = callback.from_user.id
    async with get_session() as session:
        user = await get_user_by_user_id(session, telegram_id)
        if user is None:
            await callback.answer("❌ Вы не зарегистрированы. Используйте /start", show_alert=True)
            return

        cluster = await get_cluster_by_id(session, cluster_id)
        if cluster is None:
            await callback.answer("❌ Кластер не найден", show_alert=True)
            return

        if not await is_subscription_active(session, telegram_id):
            await callback.message.edit_text(
                "⚠️ <b>Подписка истекла</b>\n\n"
                "Для получения ключей продлите подписку в разделе 💎 Подписка.",
                reply_markup=get_back_to_menu_keyboard(),
            )
            await callback.answer()
            return

        xray_client = XrayPanelClient.from_cluster(cluster)
        region_code = (cluster.region_code or "nl").lower()
        peer = await get_or_create_peer_for_cluster(
            session=session,
            user_db_id=user.id,
            user_id=user.user_id,
            cluster=cluster,
            xray_client=xray_client,
            expires_at=user.expires_at,
            key_type="standard",
            region_code=region_code,
        )

    await callback.message.delete()
    clear(callback.message.chat.id)

    await callback.message.answer(
        KEY_RECEIVED_TEMPLATE.format(location=cluster.public_name, key=peer.url)
    )

    await callback.answer("✅ Ключ получен!")
    logger.info(f"User {telegram_id} got key for cluster {cluster.id}")

    sent_info = await callback.message.answer(CLIENT_INFO)
    sent_menu = await callback.message.answer(
        MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard()
    )
    store(callback.message.chat.id, sent_info.message_id, sent_menu.message_id)


async def _issue_whitelist_key(
    callback: CallbackQuery, selected_cluster_id: UUID, selected_region_code: str
) -> None:
    telegram_id = callback.from_user.id
    async with get_session() as session:
        user = await get_user_by_user_id(session, telegram_id)
        if user is None:
            await callback.answer("❌ Вы не зарегистрированы. Используйте /start", show_alert=True)
            return

        selected_cluster = await get_cluster_by_id(session, selected_cluster_id)
        if selected_cluster is None:
            await callback.answer("❌ Кластер не найден", show_alert=True)
            return

        whitelist_cluster = await get_whitelist_cluster(session)
        if whitelist_cluster is None:
            await callback.answer(
                "❌ Кластер белых списков не настроен. Обратитесь к администратору.",
                show_alert=True,
            )
            return

        if not await is_subscription_active(session, telegram_id):
            await callback.message.edit_text(
                "⚠️ <b>Подписка истекла</b>\n\n"
                "Для получения ключей продлите подписку в разделе 💎 Подписка.",
                reply_markup=get_back_to_menu_keyboard(),
            )
            await callback.answer()
            return

        xray_client = XrayPanelClient.from_cluster(whitelist_cluster)
        peer = await get_or_create_peer_for_cluster(
            session=session,
            user_db_id=user.id,
            user_id=user.user_id,
            cluster=whitelist_cluster,
            xray_client=xray_client,
            expires_at=user.expires_at,
            key_type="whitelist",
            region_code=selected_region_code.lower(),
        )

    await callback.message.delete()
    clear(callback.message.chat.id)

    await callback.message.answer(
        KEY_RECEIVED_TEMPLATE.format(
            location=f"{selected_cluster.public_name} • Белый список",
            key=peer.url,
        )
    )

    await callback.answer("✅ Ключ получен!")
    logger.info(
        f"User {telegram_id} got whitelist key for region {selected_region_code.lower()}"
    )

    sent_info = await callback.message.answer(CLIENT_INFO)
    sent_menu = await callback.message.answer(
        MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard()
    )
    store(callback.message.chat.id, sent_info.message_id, sent_menu.message_id)


@router.message(F.text == "🔑 Получить ключ")
async def get_key_handler(message: Message):
    telegram_id = message.from_user.id

    await message.delete()
    await delete_last(message.bot, message.chat.id)

    try:
        async with get_session() as session:
            user = await get_user_by_user_id(session, telegram_id)
            if user is None:
                await message.answer("❌ Вы не зарегистрированы. Используйте /start")
                return

            if not await is_subscription_active(session, telegram_id):
                await message.answer(
                    "⚠️ <b>Подписка истекла</b>\n\n"
                    "Для получения ключей продлите подписку в разделе 💎 Подписка.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                return

            clusters = await get_standard_clusters(session)

        if not clusters:
            sent = await message.answer(
                "❌ Нет доступных регионов. Обратитесь к администратору.",
                reply_markup=get_back_to_menu_keyboard(),
            )
            store(message.chat.id, sent.message_id)
            return

        sent = await message.answer(
            SELECT_LOCATION,
            reply_markup=get_locations_keyboard(clusters),
        )
        store(message.chat.id, sent.message_id)
    except Exception as e:
        logger.error(f"Error in get_key_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "back_to_locations")
async def back_to_locations_handler(callback: CallbackQuery):
    try:
        async with get_session() as session:
            clusters = await get_standard_clusters(session)
        await callback.message.edit_text(
            SELECT_LOCATION,
            reply_markup=get_locations_keyboard(clusters),
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_locations_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("key_loc:"))
async def location_selected_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    cluster_id_raw = callback.data.removeprefix("key_loc:")

    try:
        cluster_id = UUID(cluster_id_raw)
        async with get_session() as session:
            user = await get_user_by_user_id(session, telegram_id)
            if user is None:
                await callback.answer("❌ Вы не зарегистрированы. Используйте /start", show_alert=True)
                return

            cluster = await get_cluster_by_id(session, cluster_id)
            if cluster is None:
                await callback.answer("❌ Кластер не найден", show_alert=True)
                return

            if not await is_subscription_active(session, telegram_id):
                await callback.message.edit_text(
                    "⚠️ <b>Подписка истекла</b>\n\n"
                    "Для получения ключей продлите подписку в разделе 💎 Подписка.",
                    reply_markup=get_back_to_menu_keyboard(),
                )
                await callback.answer()
                return

        region_code = (cluster.region_code or "nl").lower()
        await callback.message.edit_text(
            SELECT_KEY_MODE.format(location=cluster.public_name),
            reply_markup=get_key_mode_keyboard(str(cluster.id), region_code),
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in location_selected_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("key_mode:standard:"))
async def key_mode_standard_handler(callback: CallbackQuery):
    try:
        payload = callback.data.removeprefix("key_mode:standard:")
        cluster_id_raw = payload.split(":")[0]
        cluster_id = UUID(cluster_id_raw)
        await _issue_standard_key(callback, cluster_id)
    except Exception as e:
        logger.error(f"Error in key_mode_standard_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("key_mode:whitelist:"))
async def key_mode_whitelist_handler(callback: CallbackQuery):
    try:
        payload = callback.data.removeprefix("key_mode:whitelist:")
        if ":" in payload:
            cluster_id_raw, region_code = payload.split(":", maxsplit=1)
        else:
            cluster_id_raw = payload
            region_code = "nl"
        cluster_id = UUID(cluster_id_raw)
        await _issue_whitelist_key(callback, cluster_id, region_code)
    except Exception as e:
        logger.error(f"Error in key_mode_whitelist_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
