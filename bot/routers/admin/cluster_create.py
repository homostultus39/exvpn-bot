from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.management.dependencies import get_api_client
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.middlewares.admin import AdminMiddleware
from bot.management.logger import configure_logger

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_CLUSTER_CREATE", "red")


class ClusterCreateForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_endpoint = State()
    waiting_for_api_key = State()


@router.callback_query(F.data == "admin_create_cluster")
async def start_cluster_create(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 1/3: Введите название кластера\n"
        "(Например: 🇳🇱 Нидерланды)"
    )
    await state.set_state(ClusterCreateForm.waiting_for_name)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_name)
async def process_cluster_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 2/3: Введите endpoint кластера\n"
        "(Например: vpn-nl.example.com или 1.2.3.4:51820)"
    )
    await state.set_state(ClusterCreateForm.waiting_for_endpoint)


@router.message(ClusterCreateForm.waiting_for_endpoint)
async def process_cluster_endpoint(message: Message, state: FSMContext):
    await state.update_data(endpoint=message.text)
    await message.answer(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 3/3: Введите API ключ кластера\n"
        "(Ключ для авторизации на кластере)"
    )
    await state.set_state(ClusterCreateForm.waiting_for_api_key)


@router.message(ClusterCreateForm.waiting_for_api_key)
async def process_cluster_api_key(message: Message, state: FSMContext):
    await state.update_data(api_key=message.text)

    data = await state.get_data()

    try:
        api_client = get_api_client()
        async with api_client:
            cluster_repo = ClusterRepository(api_client)
            cluster_service = ClusterService(cluster_repo)

            cluster = await cluster_service.create_cluster(
                name=data["name"],
                endpoint=data["endpoint"],
                api_key=data["api_key"]
            )

            await message.answer(
                f"✅ <b>Кластер создан!</b>\n\n"
                f"🌐 Название: {cluster.name}\n"
                f"🆔 ID: <code>{cluster.id}</code>\n"
                f"🌍 Endpoint: {cluster.endpoint}\n\n"
                f"Кластер готов к использованию!"
            )

            logger.info(f"Admin {message.from_user.id} created cluster {cluster.id} ({cluster.name})")

    except Exception as e:
        logger.error(f"Error creating cluster: {e}")
        await message.answer(
            f"❌ Ошибка при создании кластера:\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"Проверьте введенные данные и попробуйте снова через /admin → 🌐 Кластеры"
        )

    await state.clear()
