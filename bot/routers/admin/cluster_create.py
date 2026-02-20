from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from bot.management.dependencies import get_api_client
from bot.management.fsm_utils import cancel_active_fsm
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.service import ClusterService
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import get_admin_menu_keyboard, get_fsm_keyboard
from bot.management.logger import configure_logger

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_CLUSTER_CREATE", "red")

PREFIX = "cc"


class ClusterCreateForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_endpoint = State()
    waiting_for_api_key = State()


async def _edit_prompt(bot: Bot, data: dict, text: str, keyboard) -> None:
    try:
        await bot.edit_message_text(
            chat_id=data["prompt_chat_id"],
            message_id=data["prompt_msg_id"],
            text=text,
            reply_markup=keyboard
        )
    except Exception:
        pass


async def _delete_prompt(bot: Bot, data: dict) -> None:
    try:
        await bot.delete_message(data["prompt_chat_id"], data["prompt_msg_id"])
    except Exception:
        pass


@router.callback_query(StateFilter(ClusterCreateForm), F.data == f"{PREFIX}_cancel")
async def cancel_cluster_create(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Создание кластера отменено.", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_create_cluster")
async def start_cluster_create(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    await callback.message.delete()
    msg = await callback.message.answer(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 1/3: Введите название кластера\n"
        "(Например: 🇳🇱 Нидерланды)",
        reply_markup=get_fsm_keyboard(PREFIX, back=False)
    )
    await state.update_data(prompt_msg_id=msg.message_id, prompt_chat_id=msg.chat.id)
    await state.set_state(ClusterCreateForm.waiting_for_name)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_name)
async def process_cluster_name(message: Message, state: FSMContext, bot: Bot):
    name = message.text
    await message.delete()
    await state.update_data(name=name)
    data = await state.get_data()
    await _edit_prompt(
        bot, data,
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 2/3: Введите endpoint кластера\n"
        "(Например: vpn-nl.example.com или 1.2.3.4:51820)",
        get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_endpoint)


@router.callback_query(ClusterCreateForm.waiting_for_endpoint, F.data == f"{PREFIX}_back")
async def cc_back_to_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 1/3: Введите название кластера:",
        reply_markup=get_fsm_keyboard(PREFIX, back=False)
    )
    await state.set_state(ClusterCreateForm.waiting_for_name)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_endpoint)
async def process_cluster_endpoint(message: Message, state: FSMContext, bot: Bot):
    endpoint = message.text
    await message.delete()
    await state.update_data(endpoint=endpoint)
    data = await state.get_data()
    await _edit_prompt(
        bot, data,
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 3/3: Введите API ключ кластера\n"
        "(Ключ для авторизации на кластере)",
        get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_api_key)


@router.callback_query(ClusterCreateForm.waiting_for_api_key, F.data == f"{PREFIX}_back")
async def cc_back_to_endpoint(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 2/3: Введите endpoint кластера:",
        reply_markup=get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_endpoint)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_api_key)
async def process_cluster_api_key(message: Message, state: FSMContext, bot: Bot):
    api_key = message.text
    await message.delete()
    await state.update_data(api_key=api_key)
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

        await _delete_prompt(bot, data)
        await message.answer(
            f"✅ <b>Кластер создан!</b>\n\n"
            f"🌐 Название: {cluster.name}\n"
            f"🆔 ID: <code>{cluster.id}</code>\n"
            f"🌍 Endpoint: {cluster.endpoint}\n\n"
            f"Кластер готов к использованию!",
            reply_markup=get_admin_menu_keyboard()
        )
        logger.info(f"Admin {message.from_user.id} created cluster {cluster.id} ({cluster.name})")

    except Exception as e:
        logger.error(f"Error creating cluster: {e}")
        await _edit_prompt(
            bot, data,
            f"❌ <b>Ошибка при создании кластера</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"Проверьте введённые данные и попробуйте снова:",
            get_fsm_keyboard(PREFIX, back=True)
        )
        await state.set_state(ClusterCreateForm.waiting_for_api_key)
        return

    await state.clear()
