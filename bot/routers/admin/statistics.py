from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.peer.repository import PeerRepository
from bot.middlewares.admin import AdminMiddleware
from bot.messages.admin import GENERAL_STATS_TEMPLATE, CLIENTS_STATS_TEMPLATE
from bot.utils.logger import logger

router = Router()
router.message.middleware(AdminMiddleware())

settings = get_settings()


@router.message(F.text == "📊 Статистика")
async def statistics_handler(message: Message):
    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            cluster_repo = ClusterRepository(api_client)
            peer_repo = PeerRepository(api_client)

            clients = await client_repo.list()
            clusters = await cluster_repo.list()
            peers = await peer_repo.list()

            clients_total = len(clients)
            clusters_total = len(clusters)
            clusters_active = sum(1 for c in clusters if c.is_active)
            peers_total = len(peers)

            peers_with_stats = []
            for peer in peers:
                try:
                    stats = await peer_repo.get_statistics(peer.id)
                    peers_with_stats.append(stats)
                except:
                    pass

            peers_online = sum(1 for p in peers_with_stats if p.online)

            text = GENERAL_STATS_TEMPLATE.format(
                clients_total=clients_total,
                clusters_total=clusters_total,
                clusters_active=clusters_active,
                peers_total=peers_total,
                peers_online=peers_online
            )

            await message.answer(text)

    except Exception as e:
        logger.error(f"Error in statistics_handler: {e}")
        await message.answer("❌ Произошла ошибка при загрузке статистики")


@router.message(F.text == "👥 Клиенты")
async def clients_stats_handler(message: Message):
    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            clients = await client_repo.list()

            active_count = sum(1 for c in clients if c.expires_at > datetime.utcnow())
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
