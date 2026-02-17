from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.entities.peer.repository import PeerRepository
from bot.entities.peer.service import PeerService
from bot.keyboards.user import get_location_keyboard
from bot.messages.user import SELECT_LOCATION, KEY_RECEIVED_TEMPLATE, CLIENT_INFO
from bot.core.exceptions import SubscriptionExpiredException, UserNotRegisteredException
from bot.management.logger import configure_logger

router = Router()
logger = configure_logger("LOCATIONS_ROUTER", "cyan")


@router.message(F.text == "🔑 Получить ключ")
async def get_key_handler(message: Message):
    telegram_id = message.from_user.id

    try:
        api_client = get_api_client()
        async with api_client:
            client_repo = ClientRepository(api_client)
            client_service = ClientService(client_repo)

            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)

            if not await client_service.is_registered_by_telegram_id(telegram_id):
                await message.answer("❌ Вы не зарегистрированы. Используйте /start")
                return

            clusters = await cluster_service.get_active_clusters()

            if not clusters:
                await message.answer("❌ Нет доступных регионов. Обратитесь к администратору.")
                return

            await message.answer(
                SELECT_LOCATION,
                reply_markup=get_location_keyboard(clusters)
            )
    except Exception as e:
        logger.error(f"Error in get_key_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("location_"))
async def location_selected_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    cluster_id = callback.data.split("_")[1]

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

            try:
                await client_service.ensure_active_subscription(client_id)
            except SubscriptionExpiredException:
                await callback.message.edit_text(
                    "⚠️ <b>Подписка истекла</b>\n\n"
                    "Для получения ключей необходимо продлить подписку.\n"
                    "Используйте команду /start и выберите 💎 Подписка"
                )
                await callback.answer()
                return

            from uuid import UUID
            cluster_uuid = UUID(cluster_id)
            cluster = await cluster_service.get_cluster(cluster_uuid)

            peer = await peer_service.get_or_create_peer(
                client_id=client_id,
                cluster_id=cluster_uuid,
                app_type="amnezia_wg",
                protocol="wireguard"
            )

            if peer.config:
                config_bytes = peer.config.encode('utf-8')
                config_file = BufferedInputFile(config_bytes, filename=f"exvpn_{cluster.name}.conf")

                await callback.message.answer_document(
                    document=config_file,
                    caption=KEY_RECEIVED_TEMPLATE.format(
                        CLIENT_INFO,
                        location=cluster.name,
                        app_type="AmneziaWG"
                    )
                )
            else:
                await callback.message.answer(
                    KEY_RECEIVED_TEMPLATE.format(
                        CLIENT_INFO,
                        location=cluster.name,
                        app_type="AmneziaWG"
                    ) + "\n\n⚠️ Конфиг пока не готов. Попробуйте через минуту."
                )

            await callback.answer("✅ Ключ получен!")
            logger.info(f"User {telegram_id} got key for cluster {cluster.name}")

    except UserNotRegisteredException:
        await callback.message.edit_text("❌ Вы не зарегистрированы. Используйте /start")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in location_selected_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
