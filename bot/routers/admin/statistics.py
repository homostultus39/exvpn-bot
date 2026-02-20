from uuid import UUID
from bot.management.timezone import now as get_now
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.statistics.repository import StatisticsRepository
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import (
    get_stats_keyboard, get_stats_clusters_keyboard, get_stats_back_keyboard
)
from bot.messages.admin import (
    CLIENTS_STATS_TEMPLATE, GLOBAL_STATS_TEMPLATE, CLUSTER_STATS_TEMPLATE
)
from bot.management.logger import configure_logger

router = Router()
logger = configure_logger("ADMIN_STATISTICS", "red")
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
        api_client = get_api_client()
        async with api_client:
            stats_repo = StatisticsRepository(api_client)
            stats = await stats_repo.get_global()

        text = GLOBAL_STATS_TEMPLATE.format(
            clusters_total=stats.clusters.total,
            clusters_active=stats.clusters.active,
            clusters_inactive=stats.clusters.inactive,
            clients_total=stats.clients.total,
            clients_active=stats.clients.by_status.active,
            clients_trial=stats.clients.by_status.trial,
            clients_expired=stats.clients.by_status.expired,
            peers_total=stats.peers.total,
            peers_online=stats.peers.online,
            peers_amnezia_vpn=stats.peers.by_app_type.amnezia_vpn,
            peers_amnezia_wg=stats.peers.by_app_type.amnezia_wg,
            rx=_fmt_bytes(stats.traffic.total_rx_bytes),
            tx=_fmt_bytes(stats.traffic.total_tx_bytes),
        )
        await callback.message.edit_text(text, reply_markup=get_stats_back_keyboard())
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in stats_global_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)


@router.callback_query(F.data == "admin_stats_cluster_list")
async def stats_cluster_list_handler(callback: CallbackQuery):
    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            clusters = await cluster_repo.list()

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
    cluster_id_str = callback.data.removeprefix("admin_stats_cl:")
    try:
        api_client = get_api_client()
        async with api_client:
            stats_repo = StatisticsRepository(api_client)
            stats = await stats_repo.get_cluster(UUID(cluster_id_str))

        status = "✅ Активен" if stats.cluster.is_active else "❌ Неактивен"
        text = CLUSTER_STATS_TEMPLATE.format(
            cluster_name=stats.cluster.name,
            status=status,
            container_status=stats.cluster.container_status or "—",
            protocol=stats.cluster.protocol or "—",
            clients_total=stats.clients.total,
            peers_total=stats.peers.total,
            peers_online=stats.peers.online,
            peers_amnezia_vpn=stats.peers.by_app_type.amnezia_vpn,
            peers_amnezia_wg=stats.peers.by_app_type.amnezia_wg,
            rx=_fmt_bytes(stats.traffic.total_rx_bytes),
            tx=_fmt_bytes(stats.traffic.total_tx_bytes),
        )
        await callback.message.edit_text(text, reply_markup=get_stats_back_keyboard())
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
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            clients = await client_repo.list()

            active_count = sum(1 for c in clients if c.expires_at > get_now())
            with_keys_count = sum(1 for c in clients if c.peers_count > 0)

            text = CLIENTS_STATS_TEMPLATE.format(
                total=len(clients),
                active=active_count,
                with_keys=with_keys_count
            )

            await message.answer(text)

    except Exception as e:
        logger.error(f"Error in clients_stats_handler: {e}")
        await message.answer("❌ Произошла ошибка при загрузке статистики клиентов")
