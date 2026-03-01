from datetime import datetime

import pytz
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from uuid import UUID

from bot.core.xray_panel_client import XrayPanelClient
from bot.database.connection import get_session
from bot.database.management.operations.cluster import (
    get_all_clusters,
    get_cluster_by_id,
)
from bot.database.models import PeerModel, SubscriptionStatus, UserModel
from bot.keyboards.admin import (
    get_stats_back_keyboard,
    get_stats_cluster_back_keyboard,
    get_stats_clusters_keyboard,
    get_stats_keyboard,
)
from bot.messages.admin import (
    CLIENTS_STATS_TEMPLATE,
    CLUSTER_STATS_TEMPLATE,
    GLOBAL_STATS_TEMPLATE,
)
from bot.management.logger import configure_logger
from bot.management.settings import get_settings
from bot.middlewares.admin import AdminMiddleware

router = Router()
logger = configure_logger("ADMIN_STATISTICS", "red")
settings = get_settings()
tz = pytz.timezone(settings.timezone)
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


def _fmt_bytes(b: int | None) -> str:
    if b is None:
        return "—"
    if b < 1024:
        return f"{b} Б"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} КБ"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} МБ"
    else:
        return f"{b / 1024 ** 3:.2f} ГБ"


@router.message(F.text == "📊 Статистика")
async def statistics_handler(message: Message):
    await message.answer(
        "📊 <b>Статистика</b>\n\nВыберите тип статистики:",
        reply_markup=get_stats_keyboard()
    )


@router.callback_query(F.data == "admin_stats_global")
async def stats_global_handler(callback: CallbackQuery):
    try:
        async with get_session() as session:
            clusters = await get_all_clusters(session)
            users = await session.execute(select(UserModel))
            users = list(users.scalars().all())
            peers_count_result = await session.execute(select(func.count(PeerModel.id)))
            peers_total = int(peers_count_result.scalar() or 0)

            clients_active = len(
                [
                    user for user in users
                    if user.subscription_status in (
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.UNLIMITED.value,
                    )
                ]
            )
            clients_trial = len(
                [user for user in users if user.subscription_status == SubscriptionStatus.TRIAL.value]
            )
            clients_expired = len(
                [user for user in users if user.subscription_status == SubscriptionStatus.EXPIRED.value]
            )

        text = GLOBAL_STATS_TEMPLATE.format(
            clusters_total=len(clusters),
            clusters_active=len(clusters),
            clusters_inactive=0,
            clients_total=len(users),
            clients_active=clients_active,
            clients_trial=clients_trial,
            clients_expired=clients_expired,
            peers_total=peers_total,
            peers_online=0,
            rx=_fmt_bytes(0),
            tx=_fmt_bytes(0),
        )
        await callback.message.edit_text(text, reply_markup=get_stats_back_keyboard())
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in stats_global_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)


@router.callback_query(F.data == "admin_stats_cluster_list")
async def stats_cluster_list_handler(callback: CallbackQuery):
    try:
        async with get_session() as session:
            clusters = await get_all_clusters(session)

        await callback.message.edit_text(
            "🌐 <b>Статистика по кластеру</b>\n\nВыберите кластер:",
            reply_markup=get_stats_clusters_keyboard(clusters)
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in stats_cluster_list_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке кластеров", show_alert=True)


@router.callback_query(F.data.startswith("admin_stats_cl:"))
async def stats_cluster_handler(callback: CallbackQuery):
    cluster_id_raw = callback.data.removeprefix("admin_stats_cl:")
    try:
        cluster_id = UUID(cluster_id_raw)
        async with get_session() as session:
            cluster = await get_cluster_by_id(session, cluster_id)
            if cluster is None:
                await callback.answer("❌ Кластер не найден", show_alert=True)
                return
            clients_total_result = await session.execute(
                select(func.count(PeerModel.id)).where(PeerModel.cluster_id == cluster.id)
            )
            clients_total = int(clients_total_result.scalar() or 0)

        panel_client = XrayPanelClient.from_cluster(cluster)
        stats = await panel_client.get_cluster_stats()

        text = CLUSTER_STATS_TEMPLATE.format(
            cluster_name=cluster.public_name,
            status="✅ Доступен",
            inbounds_total=stats["inbounds_total"],
            clients_total=clients_total,
            peers_total=clients_total,
            peers_online=stats["clients_online"],
            rx=_fmt_bytes(stats["rx_bytes"]),
            tx=_fmt_bytes(stats["tx_bytes"]),
        )
        await callback.message.edit_text(text, reply_markup=get_stats_cluster_back_keyboard())
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in stats_cluster_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики кластера", show_alert=True)


@router.callback_query(F.data == "admin_stats_back")
async def stats_back_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Статистика</b>\n\nВыберите тип статистики:",
        reply_markup=get_stats_keyboard()
    )
    await callback.answer()


@router.message(F.text == "👥 Клиенты")
async def clients_stats_handler(message: Message):
    try:
        async with get_session() as session:
            users_result = await session.execute(select(UserModel))
            users = list(users_result.scalars().all())
            active_count = sum(
                1 for user in users if user.expires_at is None or user.expires_at > datetime.now(tz)
            )

            with_keys_result = await session.execute(
                select(func.count(func.distinct(PeerModel.client_id)))
            )
            with_keys_count = int(with_keys_result.scalar() or 0)

        text = CLIENTS_STATS_TEMPLATE.format(
            total=len(users),
            active=active_count,
            with_keys=with_keys_count
        )

        await message.answer(text)

    except Exception as e:
        logger.error(f"Error in clients_stats_handler: {e}")
        await message.answer("❌ Произошла ошибка при загрузке статистики клиентов")
