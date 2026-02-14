from uuid import UUID
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from bot.management.settings import get_settings
from bot.management.dependencies import get_api_client
from bot.entities.user.storage import UserStorage
from bot.entities.user.service import UserService
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.entities.peer.repository import PeerRepository
from bot.entities.peer.service import PeerService
from bot.keyboards.user import get_location_keyboard
from bot.messages.user import SELECT_LOCATION, KEY_RECEIVED_TEMPLATE, KEY_ALREADY_EXISTS_TEMPLATE
from bot.core.exceptions import SubscriptionExpiredException, UserNotRegisteredException
from bot.utils.logger import logger

router = Router()
settings = get_settings()


async def get_services():
    storage = UserStorage(settings.database_path)
    await storage.init_db()

    api_client = get_api_client()
    async with api_client:
        client_repo = ClientRepository(api_client)
        client_service = ClientService(client_repo)
        user_service = UserService(storage, client_service)

        cluster_repo = ClusterRepository(api_client)
        cluster_service = ClusterService(cluster_repo, settings)

        peer_repo = PeerRepository(api_client)
        peer_service = PeerService(peer_repo)

        return user_service, client_service, cluster_service, peer_service, api_client


@router.message(F.text == "🔑 Получить ключ")
async def get_key_handler(message: Message):
    telegram_id = message.from_user.id

    try:
        user_service, _, _, _, _ = await get_services()

        if not await user_service.is_registered(telegram_id):
            await message.answer("❌ Вы не зарегистрированы. Используйте /start")
            return

        if not await user_service.has_agreed_to_terms(telegram_id):
            await message.answer("❌ Необходимо принять условия использования. Используйте /start")
            return

        clusters = settings.clusters
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
    location_code = callback.data.split("_")[1]

    try:
        user_service, client_service, cluster_service, peer_service, api_client = await get_services()

        client_id = await user_service.get_client_id(telegram_id)

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

        cluster = await cluster_service.get_cluster_by_code(location_code)
        if not cluster:
            await callback.answer("❌ Регион не найден", show_alert=True)
            return

        cluster_uuid = UUID(next(c.uuid for c in settings.clusters if c.code == location_code))

        peer = await peer_service.get_or_create_peer(
            client_id=client_id,
            cluster_id=cluster_uuid,
            app_type="amnezia_wg",
            protocol="wireguard"
        )

        location_name = next(c.name for c in settings.clusters if c.code == location_code)

        if peer.config:
            config_bytes = peer.config.encode('utf-8')
            config_file = BufferedInputFile(config_bytes, filename=f"exvpn_{location_code}.conf")

            await callback.message.answer_document(
                document=config_file,
                caption=KEY_RECEIVED_TEMPLATE.format(
                    location=location_name,
                    app_type="AmneziaWG"
                )
            )
        else:
            await callback.message.answer(
                KEY_RECEIVED_TEMPLATE.format(
                    location=location_name,
                    app_type="AmneziaWG"
                ) + "\n\n⚠️ Конфиг пока не готов. Попробуйте через минуту."
            )

        await callback.answer("✅ Ключ получен!")
        logger.info(f"User {telegram_id} got key for {location_code}")

    except UserNotRegisteredException:
        await callback.message.edit_text("❌ Вы не зарегистрированы. Используйте /start")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in location_selected_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
