from datetime import datetime
from bot.management.timezone import get_timezone, now as get_now
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.entities.peer.repository import PeerRepository
from bot.entities.peer.service import PeerService
from bot.keyboards.user import get_profile_keyboard
from bot.messages.user import (
    PROFILE_MESSAGE_TEMPLATE,
    SUBSCRIPTION_ACTIVE_TEMPLATE,
    SUBSCRIPTION_EXPIRED
)
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last

router = Router()
logger = configure_logger("PROFILE_ROUTER", "magenta")


@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message):
    telegram_id = message.from_user.id
    username = message.from_user.username or f"user_{telegram_id}"

    await message.delete()
    await delete_last(message.bot, message.chat.id)

    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)

            peer_repo = PeerRepository(api_client)
            peer_service = PeerService(peer_repo)

            client_id = await client_service.get_client_id_by_telegram_id(telegram_id)
            client = await client_service.get_client(client_id)

            if client.expires_at > get_now():
                local_expires_at = client.expires_at.astimezone(get_timezone())
                subscription_status = SUBSCRIPTION_ACTIVE_TEMPLATE.format(
                    expires_at=local_expires_at.strftime("%d.%m.%Y %H:%M")
                )
            else:
                subscription_status = SUBSCRIPTION_EXPIRED

            peers = await peer_service.get_client_peers(client_id)

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

    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)

            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)

            peer_repo = PeerRepository(api_client)
            peer_service = PeerService(peer_repo)

            client_id = await client_service.get_client_id_by_telegram_id(telegram_id)
            peers = await peer_service.get_client_peers(client_id)

            if not peers:
                await callback.message.edit_text(
                    "🔑 <b>Мои ключи</b>\n\n"
                    "У вас пока нет активных ключей.\n"
                    "Используйте 🔑 Получить ключ для создания."
                )
                await callback.answer()
                return

            keys_text = "🔑 <b>Мои ключи</b>\n\n"
            for i, peer in enumerate(peers, 1):
                try:
                    cluster = await cluster_service.get_cluster(peer.cluster_id)
                    cluster_name = cluster.name
                except:
                    cluster_name = "Неизвестно"

                keys_text += f"{i}. {cluster_name}\n"
                keys_text += f"   IP: <code>{peer.allocated_ip}</code>\n"
                keys_text += f"   Создан: {peer.created_at.strftime('%d.%m.%Y')}\n\n"

            await callback.message.edit_text(keys_text)
            await callback.answer()

    except Exception as e:
        logger.error(f"Error in my_keys_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
