from uuid import UUID
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from bot.management.dependencies import get_api_client
from bot.entities.client.repository import ClientRepository
from bot.entities.client.service import ClientService
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.entities.peer.repository import PeerRepository
from bot.entities.peer.service import PeerService
from bot.keyboards.user import get_location_keyboard, get_app_type_keyboard, get_main_menu_keyboard, get_back_to_menu_keyboard
from bot.messages.user import SELECT_LOCATION, SELECT_APP_TYPE, KEY_RECEIVED_TEMPLATE, MAIN_MENU_MESSAGE, CLIENT_INFO
from bot.core.exceptions import SubscriptionExpiredException, UserNotRegisteredException
from bot.management.logger import configure_logger
from bot.management.message_tracker import store, delete_last, clear

router = Router()
logger = configure_logger("LOCATIONS_ROUTER", "cyan")



@router.message(F.text == "🔑 Получить ключ")
async def get_key_handler(message: Message):
    telegram_id = message.from_user.id

    await message.delete()
    await delete_last(message.bot, message.chat.id)

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
                sent = await message.answer(
                    "❌ Нет доступных регионов. Обратитесь к администратору.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                store(message.chat.id, sent.message_id)
                return

            sent = await message.answer(
                SELECT_LOCATION,
                reply_markup=get_location_keyboard(clusters)
            )
            store(message.chat.id, sent.message_id)
    except Exception as e:
        logger.error(f"Error in get_key_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("loc:"))
async def location_selected_handler(callback: CallbackQuery):
    cluster_id = callback.data.split(":", 1)[1]

    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)

            cluster = await cluster_service.get_cluster(UUID(cluster_id))

            await callback.message.edit_text(
                SELECT_APP_TYPE.format(cluster_name=cluster.name),
                reply_markup=get_app_type_keyboard(cluster_id, cluster.name)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in location_selected_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_locations")
async def back_to_locations_handler(callback: CallbackQuery):
    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)

            clusters = await cluster_service.get_active_clusters()

            await callback.message.edit_text(
                SELECT_LOCATION,
                reply_markup=get_location_keyboard(clusters)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_locations_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("key:"))
async def generate_key_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    _, cluster_id, app_type = callback.data.split(":")

    app_type_label = "AmneziaVPN" if app_type == "amnezia_vpn" else "AmneziaWG"

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

            cluster_uuid = UUID(cluster_id)
            cluster = await cluster_service.get_cluster(cluster_uuid)

            peer = await peer_service.get_or_create_peer(
                client_id=client_id,
                cluster_id=cluster_uuid,
                app_type=app_type,
            )

            caption = KEY_RECEIVED_TEMPLATE.format(
                location=cluster.name,
                app_type=app_type_label
            )

            await callback.message.delete()
            clear(callback.message.chat.id)

            if peer.config:
                config_bytes = peer.config.encode("utf-8")
                config_file = BufferedInputFile(
                    config_bytes,
                    filename=f"amnezia_{app_type.split('_')[-1]}.conf"
                )
                await callback.message.answer_document(
                    document=config_file,
                    caption=caption
                )
            else:
                await callback.message.answer(
                    caption + "\n\n⚠️ Конфиг пока не готов. Попробуйте через минуту."
                )

            await callback.answer("✅ Ключ получен!")
            logger.info(f"User {telegram_id} got key for cluster {cluster.name}, app_type={app_type}")

            sent_info = await callback.message.answer(CLIENT_INFO)
            sent_menu = await callback.message.answer(MAIN_MENU_MESSAGE, reply_markup=get_main_menu_keyboard())
            store(callback.message.chat.id, sent_info.message_id, sent_menu.message_id)

    except UserNotRegisteredException:
        await callback.message.edit_text("❌ Вы не зарегистрированы. Используйте /start")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in generate_key_handler: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
