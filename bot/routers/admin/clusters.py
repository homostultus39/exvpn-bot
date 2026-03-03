from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from uuid import UUID

from bot.database.connection import get_session
from bot.database.management.operations.cluster import (
    delete_cluster,
    get_all_clusters,
    get_cluster_by_id,
    get_clusters_peers_count,
    get_or_create_cluster,
    update_cluster,
)
from bot.keyboards.admin import (
    get_admin_menu_keyboard,
    get_cluster_actions_keyboard,
    get_cluster_edit_keyboard,
    get_clusters_keyboard,
    get_fsm_keyboard,
    get_yes_no_keyboard,
)
from bot.management.logger import configure_logger
from bot.middlewares.admin import AdminMiddleware
from bot.middlewares.fsm_cancel import cancel_active_fsm
from bot.messages.admin import CLUSTER_INFO_TEMPLATE, CLUSTERS_LIST_TEMPLATE

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

logger = configure_logger("ADMIN_CLUSTERS", "red")

_FIELD_LABELS = {
    "public_name": "Название",
    "endpoint": "Endpoint",
    "username": "Username",
    "password": "Password",
    "is_whitelist_gateway": "Тип (whitelist)",
    "region_code": "Код региона",
}


def _cluster_type_label(is_whitelist_gateway: bool) -> str:
    return "Whitelist" if is_whitelist_gateway else "Standard"


def _validate_and_normalize_region_code(raw_value: str) -> str | None:
    normalized = raw_value.strip().lower()
    if normalized in {"-", "none", "null", "пусто"}:
        return None
    cleaned = "".join(char for char in normalized if char.isalnum() or char == "-")
    return cleaned or None


def _parse_region_code_value(raw_value: str) -> str | None:
    normalized = _validate_and_normalize_region_code(raw_value)
    if normalized is None:
        raise ValueError("Укажите непустой region_code без лишних символов.")
    return normalized

class ClusterState(StatesGroup):
    cluster_id = State()

    edit_field = State()
    edit_value = State()
    edit_choice = State()


@router.message(F.text == "🌐 Кластеры")
async def clusters_list_handler(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    try:
        clusters_list = ""
        async with get_session() as session:
            clusters = await get_all_clusters(session)
            for cluster in clusters:
                count_peers = await get_clusters_peers_count(session, cluster.id)
                cluster_type = _cluster_type_label(cluster.is_whitelist_gateway)
                region_code = (cluster.region_code or "—").upper()
                clusters_list += f"<b>{cluster.public_name}</b>\n" 
                clusters_list += f"   Тип: {cluster_type}, регион: {region_code}\n"
                clusters_list += f"   Пиров: {count_peers}\n\n"

        text = CLUSTERS_LIST_TEMPLATE.format(
            total=len(clusters),
            clusters_list=clusters_list
        )

        await message.answer(
            text,
            reply_markup=get_clusters_keyboard(clusters)
        )

    except Exception as e:
        logger.error(f"Error in clusters_list_handler: {e}")
        await message.answer("❌ Произошла ошибка при загрузке кластеров")


@router.callback_query(F.data.startswith("admin_cluster_view_"))
async def cluster_info_handler(callback: CallbackQuery):
    cluster_id_raw = callback.data.removeprefix("admin_cluster_view_")

    try:
        cluster_id = UUID(cluster_id_raw)
        async with get_session() as session:
            cluster = await get_cluster_by_id(session, cluster_id)
            if cluster is None:
                await callback.answer("❌ Кластер не найден", show_alert=True)
                return
            peer_count = await get_clusters_peers_count(session, cluster.id)

        text = CLUSTER_INFO_TEMPLATE.format(
            name=cluster.public_name,
            id=cluster.id,
            endpoint=cluster.endpoint,
            cluster_type=_cluster_type_label(cluster.is_whitelist_gateway),
            region_code=cluster.region_code or "—",
            total_peers=peer_count,
        )

        await callback.message.edit_text(
            text,
            reply_markup=get_cluster_actions_keyboard(str(cluster.id))
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in cluster_info_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке информации", show_alert=True)

# Редактирование кластеров

@router.callback_query(F.data.startswith("admin_cluster_edit_"))
async def cluster_edit_handler(callback: CallbackQuery, state: FSMContext):
    cluster_id = callback.data.removeprefix("admin_cluster_edit_")

    await state.set_state(ClusterState.edit_choice)
    await state.update_data(cluster_id=cluster_id)

    await callback.message.edit_text(
        "✏️ <b>Редактирование кластера</b>\n\nВыберите поле для изменения:",
        reply_markup=get_cluster_edit_keyboard(cluster_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cef:"))
async def cluster_edit_field_handler(callback: CallbackQuery, state: FSMContext):
    field = callback.data.removeprefix("cef:")
    label = _FIELD_LABELS.get(field, field)
    await state.update_data(
        edit_field=field,
        prompt_msg_id=callback.message.message_id,
        prompt_chat_id=callback.message.chat.id,
    )
    if field == "is_whitelist_gateway":
        await state.set_state(ClusterState.edit_choice)
        await callback.message.edit_text(
            f"✏️ Выберите новое значение для <b>{label}</b>:",
            reply_markup=get_yes_no_keyboard("cef_bool", back=True, cancel=False),
        )
    else:
        await state.set_state(ClusterState.edit_value)
        await callback.message.edit_text(
            f"✏️ Введите новое значение для <b>{label}</b>:",
            reply_markup=get_fsm_keyboard(CEF_PREFIX, back=True)
        )
    await callback.answer()


@router.callback_query(ClusterState.edit_choice, F.data.startswith("cef_bool_"))
async def cluster_edit_bool_handler(callback: CallbackQuery, state: FSMContext):
    action = callback.data.removeprefix("cef_bool_")
    data = await state.get_data()
    cluster_id_raw = data.get("cluster_id")
    field = data.get("edit_field")
    if not cluster_id_raw or field != "is_whitelist_gateway":
        await callback.answer("❌ Неверное состояние формы.", show_alert=True)
        await state.clear()
        return

    if action == "back":
        await callback.message.edit_text(
            "✏️ <b>Редактирование кластера</b>\n\nВыберите поле для изменения:",
            reply_markup=get_cluster_edit_keyboard(cluster_id_raw),
        )
        await callback.answer()
        return
    if action not in {"yes", "no"}:
        await callback.answer("❌ Некорректное значение.", show_alert=True)
        return

    value = action == "yes"
    try:
        cluster_id = UUID(cluster_id_raw)
        async with get_session() as session:
            cluster = await get_cluster_by_id(session, cluster_id)
            if cluster is None:
                await callback.answer("❌ Кластер не найден", show_alert=True)
                await state.clear()
                return
            cluster = await update_cluster(
                session,
                cluster.id,
                is_whitelist_gateway=value,
            )
            if cluster is None:
                await callback.answer("❌ Кластер не найден", show_alert=True)
                await state.clear()
                return
            peers_count = await get_clusters_peers_count(session, cluster.id)

        await state.clear()
        text = CLUSTER_INFO_TEMPLATE.format(
            id=cluster.id,
            name=cluster.public_name,
            endpoint=cluster.endpoint,
            cluster_type=_cluster_type_label(cluster.is_whitelist_gateway),
            region_code=cluster.region_code or "—",
            total_peers=peers_count,
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_cluster_actions_keyboard(str(cluster.id)),
        )
        await callback.message.answer("🔐 Вы в главном меню.", reply_markup=get_admin_menu_keyboard())
        logger.info(
            f"Cluster {cluster_id_raw} field '{field}' updated by admin {callback.from_user.id}"
        )
        await callback.answer("✅ Значение обновлено")
    except Exception as e:
        logger.error(f"Error updating cluster bool field: {e}")
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)


@router.callback_query(ClusterState.edit_value, F.data == f"{CEF_PREFIX}_back")
async def cluster_edit_value_back_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cluster_id_raw = data.get("cluster_id")
    if not cluster_id_raw:
        await callback.answer("❌ Неверное состояние формы.", show_alert=True)
        await state.clear()
        return

    await state.set_state(ClusterState.edit_choice)
    await callback.message.edit_text(
        "✏️ <b>Редактирование кластера</b>\n\nВыберите поле для изменения:",
        reply_markup=get_cluster_edit_keyboard(cluster_id_raw),
    )
    await callback.answer()


@router.callback_query(ClusterState.edit_value, F.data == f"{CEF_PREFIX}_cancel")
async def cluster_edit_value_cancel_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await _delete_prompt(bot, data)
    await state.clear()
    await callback.message.answer("❌ Редактирование кластера отменено.", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.message(ClusterState.edit_value)
async def tariff_edit_value(message: Message, state: FSMContext, bot: Bot):
    value = message.text.strip()
    await message.delete()
    data = await state.get_data()
    cluster_id_raw = data["cluster_id"]
    field = data["edit_field"]
    label = _FIELD_LABELS.get(field, field)

    try:
        if field == "region_code":
            value = _parse_region_code_value(value)

        cluster_id = UUID(cluster_id_raw)
        async with get_session() as session:
            cluster = await get_cluster_by_id(session, cluster_id)
            if cluster is None:
                await _edit_prompt(
                    bot, data, "❌ Кластер не найден.", None
                )
                await bot.send_message(
                    data["prompt_chat_id"],
                    "🔐 Вы в главном меню.",
                    reply_markup=get_admin_menu_keyboard(),
                )
                await state.clear()
                return
            cluster = await update_cluster(
                session,
                cluster.id,
                **{field: value},
                force_update_region_code=(field == "region_code"),
            )
            if cluster is None:
                await _edit_prompt(
                    bot, data, "❌ Кластер не найден.", None
                )
                await bot.send_message(
                    data["prompt_chat_id"],
                    "🔐 Вы в главном меню.",
                    reply_markup=get_admin_menu_keyboard(),
                )
                await state.clear()
                return
            peers_count = await get_clusters_peers_count(session, cluster.id)
        
        await state.clear()

        text = CLUSTER_INFO_TEMPLATE.format(
            id=cluster.id,
            name=cluster.public_name,
            endpoint=cluster.endpoint,
            cluster_type=_cluster_type_label(cluster.is_whitelist_gateway),
            region_code=cluster.region_code or "—",
            total_peers=peers_count,
        )
        await _edit_prompt(bot, data, text, get_cluster_actions_keyboard(str(cluster.id)))
        await bot.send_message(
            data["prompt_chat_id"],
            "🔐 Вы в главном меню.",
            reply_markup=get_admin_menu_keyboard(),
        )
        logger.info(
            f"Cluster {cluster_id_raw} field '{field}' updated by admin {message.from_user.id}"
        )

    except ValueError as e:
        await _edit_prompt(
            bot, data,
            f"✏️ Введите новое значение для <b>{label}</b>:\n\n"
            f"❌ {str(e) or 'Некорректное значение. Попробуйте ещё раз.'}",
            get_fsm_keyboard(CEF_PREFIX, back=True),
        )
    except Exception as e:
        logger.error(f"Error updating tariff: {e}")
        await _edit_prompt(
            bot, data,
            f"✏️ Введите новое значение для <b>{label}</b>:\n\n"
            f"❌ Ошибка при обновлении: <code>{str(e)}</code>\n"
            f"Попробуйте ещё раз:",
            get_fsm_keyboard(CEF_PREFIX, back=True),
        )

@router.callback_query(F.data.startswith("admin_cluster_delete_"))
async def cluster_delete_handler(callback: CallbackQuery):
    cluster_id_raw = callback.data.removeprefix("admin_cluster_delete_")

    try:
        cluster_id = UUID(cluster_id_raw)
        async with get_session() as session:
            cluster = await get_cluster_by_id(session, cluster_id)
            if cluster is None:
                await callback.answer("❌ Кластер не найден", show_alert=True)
                return
            deleted = await delete_cluster(session, cluster.id)

        if deleted:
            await callback.answer("✅ Кластер удалён", show_alert=True)
            await callback.message.delete()
            await callback.message.answer("🔐 Вы в главном меню.", reply_markup=get_admin_menu_keyboard())
            logger.info(f"Cluster {cluster_id_raw} deleted by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error in cluster_delete_handler: {e}")
        await callback.answer("❌ Ошибка при удалении кластера", show_alert=True)


@router.callback_query(F.data == "admin_clusters_back")
async def clusters_back_handler(callback: CallbackQuery):
    try:
        clusters_list = ""
        async with get_session() as session:
            clusters = await get_all_clusters(session)
            for cluster in clusters:
                count_peers = await get_clusters_peers_count(session, cluster.id)
                cluster_type = _cluster_type_label(cluster.is_whitelist_gateway)
                region_code = (cluster.region_code or "—").upper()
                clusters_list += f"<b>{cluster.public_name}</b>\n" 
                clusters_list += f"   Тип: {cluster_type}, регион: {region_code}\n"
                clusters_list += f"   Пиров: {count_peers}\n\n"

        text = CLUSTERS_LIST_TEMPLATE.format(
            total=len(clusters),
            clusters_list=clusters_list
        )

        await callback.message.edit_text(
            text,
            reply_markup=get_clusters_keyboard(clusters)
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in clusters_back_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке кластеров", show_alert=True)


# Дальше - логика создания и регистрации кластеров

PREFIX = "cc"
CEF_PREFIX = "cef"


class ClusterCreateForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_endpoint = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_cluster_type = State()
    waiting_for_region_code = State()


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
    await callback.message.delete()
    msg = await callback.message.answer(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 1/6: Введите название кластера\n"
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
        "Шаг 2/6: Введите endpoint кластера\n"
        "(Например: vpn-nl.example.com или 1.2.3.4:443)",
        get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_endpoint)


@router.callback_query(ClusterCreateForm.waiting_for_endpoint, F.data == f"{PREFIX}_back")
async def cc_back_to_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 1/6: Введите название кластера\n"
        "(Например: 🇳🇱 Нидерланды)",
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
        "Шаг 3/6: Введите имя пользователя кластера\n"
        "(Имя пользователя для авторизации на кластере)",
        get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_username)


@router.callback_query(ClusterCreateForm.waiting_for_username, F.data == f"{PREFIX}_back")
async def cc_back_to_endpoint(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 2/6: Введите endpoint кластера\n"
        "(Например: vpn-nl.example.com или 1.2.3.4:443)",
        reply_markup=get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_endpoint)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_username)
async def process_cluster_username(message: Message, state: FSMContext, bot: Bot):
    username = message.text
    await message.delete()
    await state.update_data(username=username)
    data = await state.get_data()
    await _edit_prompt(
        bot, data,
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 4/6: Введите пароль пользователя кластера\n"
        "(Пароль для авторизации на кластере)",
        get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_password)


@router.callback_query(ClusterCreateForm.waiting_for_password, F.data == f"{PREFIX}_back")
async def cc_back_to_username(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 3/6: Введите имя пользователя кластера\n"
        "(Имя пользователя для авторизации на кластере)",
        reply_markup=get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_username)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_password)
async def process_cluster_password(message: Message, state: FSMContext, bot: Bot):
    password = message.text
    await message.delete()
    await state.update_data(password=password)
    data = await state.get_data()

    await _edit_prompt(
        bot, data,
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 5/6: Белые списки?",
        get_yes_no_keyboard(PREFIX, back=True, cancel=True),
    )
    await state.set_state(ClusterCreateForm.waiting_for_cluster_type)


@router.callback_query(ClusterCreateForm.waiting_for_cluster_type, F.data == f"{PREFIX}_back")
async def cc_back_to_password(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 4/6: Введите пароль пользователя кластера\n"
        "(Пароль для авторизации на кластере)",
        reply_markup=get_fsm_keyboard(PREFIX, back=True)
    )
    await state.set_state(ClusterCreateForm.waiting_for_password)
    await callback.answer()


@router.callback_query(ClusterCreateForm.waiting_for_cluster_type, F.data == f"{PREFIX}_yes")
async def cc_type_whitelist(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.update_data(is_whitelist_gateway=True, region_code=None)
    data = await state.get_data()
    await _create_cluster_from_state(callback.from_user.id, bot, data, state)
    await callback.answer()


@router.callback_query(ClusterCreateForm.waiting_for_cluster_type, F.data == f"{PREFIX}_no")
async def cc_type_standard(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_whitelist_gateway=False)
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 6/6: Введите код региона\n"
        "(Например: nl, de, fi, us-west)",
        reply_markup=get_fsm_keyboard(PREFIX, back=True),
    )
    await state.set_state(ClusterCreateForm.waiting_for_region_code)
    await callback.answer()


@router.callback_query(ClusterCreateForm.waiting_for_region_code, F.data == f"{PREFIX}_back")
async def cc_back_to_type(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Создание кластера</b>\n\n"
        "Шаг 5/6: Белые списки?",
        reply_markup=get_yes_no_keyboard(PREFIX, back=True, cancel=True),
    )
    await state.set_state(ClusterCreateForm.waiting_for_cluster_type)
    await callback.answer()


@router.message(ClusterCreateForm.waiting_for_region_code)
async def cc_enter_region_code(message: Message, state: FSMContext, bot: Bot):
    region_code_raw = message.text or ""
    await message.delete()
    data = await state.get_data()
    try:
        region_code = _parse_region_code_value(region_code_raw)
        if region_code is None:
            raise ValueError("Для стандартного кластера region_code не может быть пустым.")
    except ValueError as e:
        await _edit_prompt(
            bot,
            data,
            "➕ <b>Создание кластера</b>\n\n"
            "Шаг 6/6: Введите код региона\n"
            "(Например: nl, de, fi, us-west)\n\n"
            f"❌ {e}",
            get_fsm_keyboard(PREFIX, back=True),
        )
        return

    await state.update_data(region_code=region_code)
    data = await state.get_data()
    await _create_cluster_from_state(message.from_user.id, bot, data, state)


async def _create_cluster_from_state(
    admin_user_id: int,
    bot: Bot,
    data: dict,
    state: FSMContext,
) -> None:
    try:
        async with get_session() as session:
            cluster = await get_or_create_cluster(
                session,
                public_name=data["name"],
                endpoint=data["endpoint"],
                username=data["username"],
                password=data["password"],
                is_whitelist_gateway=bool(data.get("is_whitelist_gateway", False)),
                region_code=data.get("region_code"),
            )

        await _delete_prompt(bot, data)
        await bot.send_message(
            chat_id=data["prompt_chat_id"],
            text=(
                "✅ <b>Кластер создан!</b>\n\n"
                f"🌐 Название: {cluster.public_name}\n"
                f"🆔 ID: <code>{cluster.id}</code>\n"
                f"🌍 Endpoint: {cluster.endpoint}\n"
                f"🧭 Тип: {_cluster_type_label(cluster.is_whitelist_gateway)}\n"
                f"🏷 Регион: {cluster.region_code or '—'}\n\n"
                "Кластер готов к использованию!"
            ),
            reply_markup=get_admin_menu_keyboard(),
        )
        logger.info(
            f"Admin {admin_user_id} created cluster {cluster.id} ({cluster.public_name})"
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error creating cluster: {e}")
        await _edit_prompt(
            bot, data,
            f"❌ <b>Ошибка при создании кластера</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"Проверьте введённые данные и попробуйте снова:",
            get_yes_no_keyboard(PREFIX, back=True, cancel=True),
        )
        await state.set_state(ClusterCreateForm.waiting_for_cluster_type)
    