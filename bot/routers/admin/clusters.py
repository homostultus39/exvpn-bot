from uuid import UUID
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import get_clusters_keyboard, get_cluster_actions_keyboard
from bot.messages.admin import CLUSTERS_LIST_TEMPLATE, CLUSTER_INFO_TEMPLATE
from bot.utils.logger import logger

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

settings = get_settings()


@router.message(F.text == "🌐 Кластеры")
async def clusters_list_handler(message: Message):
    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)
            clusters = await cluster_service.list_clusters()

            active_count = sum(1 for c in clusters if c.is_active)

            clusters_list = ""
            for cluster in clusters:
                status_emoji = "✅" if cluster.is_active else "❌"
                clusters_list += f"{status_emoji} <b>{cluster.name}</b>\n"
                clusters_list += f"   Пиров: {cluster.online_peers_count}/{cluster.peers_count}\n\n"

            text = CLUSTERS_LIST_TEMPLATE.format(
                total=len(clusters),
                active=active_count,
                clusters_list=clusters_list
            )

            await message.answer(
                text,
                reply_markup=get_clusters_keyboard(clusters)
            )

    except Exception as e:
        logger.error(f"Error in clusters_list_handler: {e}")
        await message.answer("❌ Произошла ошибка при загрузке кластеров")


@router.callback_query(F.data.startswith("admin_cluster_") & ~F.data.contains("restart") & ~F.data.contains("back"))
async def cluster_info_handler(callback: CallbackQuery):
    cluster_id = callback.data.split("_")[2]

    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)
            cluster = await cluster_service.get_cluster(UUID(cluster_id))

            status = "✅ Активен" if cluster.is_active else "❌ Неактивен"
            last_handshake = cluster.last_handshake.strftime("%d.%m.%Y %H:%M") if cluster.last_handshake else "Нет данных"

            text = CLUSTER_INFO_TEMPLATE.format(
                name=cluster.name,
                id=cluster.id,
                endpoint=cluster.endpoint,
                status=status,
                online_peers=cluster.online_peers_count,
                total_peers=cluster.peers_count,
                container_status=cluster.container_status or "Неизвестно",
                last_handshake=last_handshake
            )

            await callback.message.edit_text(
                text,
                reply_markup=get_cluster_actions_keyboard(str(cluster.id))
            )
            await callback.answer()

    except Exception as e:
        logger.error(f"Error in cluster_info_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке информации", show_alert=True)


@router.callback_query(F.data.startswith("admin_cluster_restart_"))
async def cluster_restart_handler(callback: CallbackQuery):
    cluster_id = callback.data.split("_")[3]

    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)
            result = await cluster_service.restart_cluster(UUID(cluster_id))

            await callback.answer(f"✅ {result.message}", show_alert=True)
            logger.info(f"Cluster {cluster_id} restarted by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error in cluster_restart_handler: {e}")
        await callback.answer("❌ Ошибка при перезапуске кластера", show_alert=True)


@router.callback_query(F.data == "admin_clusters_back")
async def clusters_back_handler(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "admin_clusters_refresh")
async def clusters_refresh_handler(callback: CallbackQuery):
    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)
            clusters = await cluster_service.list_clusters()

            active_count = sum(1 for c in clusters if c.is_active)

            clusters_list = ""
            for cluster in clusters:
                status_emoji = "✅" if cluster.is_active else "❌"
                clusters_list += f"{status_emoji} <b>{cluster.name}</b>\n"
                clusters_list += f"   Пиров: {cluster.online_peers_count}/{cluster.peers_count}\n\n"

            text = CLUSTERS_LIST_TEMPLATE.format(
                total=len(clusters),
                active=active_count,
                clusters_list=clusters_list
            )

            await callback.message.edit_text(
                text,
                reply_markup=get_clusters_keyboard(clusters)
            )
            await callback.answer("✅ Обновлено")

    except Exception as e:
        logger.error(f"Error in clusters_refresh_handler: {e}")
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)
