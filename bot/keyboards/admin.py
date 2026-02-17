from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🌐 Кластеры"), KeyboardButton(text="👥 Клиенты")],
        [KeyboardButton(text="💳 Тарифы"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="◀️ Выход из админ-панели")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_clusters_keyboard(clusters: list) -> InlineKeyboardMarkup:
    buttons = []
    for cluster in clusters:
        status_emoji = "✅" if cluster.is_active else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {cluster.name}",
            callback_data=f"admin_cluster_{cluster.id}"
        )])
    buttons.append([InlineKeyboardButton(
        text="➕ Создать кластер",
        callback_data="admin_create_cluster"
    )])
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="admin_clusters_refresh"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cluster_actions_keyboard(cluster_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="🔄 Перезапустить",
            callback_data=f"admin_cluster_restart_{cluster_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin_clusters_back"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_clients_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="👤 Регистрация клиента",
            callback_data="admin_register_client"
        )],
        [InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="admin_clients_refresh"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tariffs_keyboard(tariffs: list) -> InlineKeyboardMarkup:
    buttons = []
    for tariff in sorted(tariffs, key=lambda t: t.sort_order):
        status_emoji = "✅" if tariff.is_active else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {tariff.name} ({tariff.code})",
            callback_data=f"admin_tariff_{tariff.id}"
        )])
    buttons.append([InlineKeyboardButton(
        text="➕ Создать тариф",
        callback_data="admin_create_tariff"
    )])
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="admin_tariffs_refresh"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tariff_actions_keyboard(tariff_id: str, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Деактивировать" if is_active else "✅ Активировать"
    buttons = [
        [InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"admin_tariff_edit_{tariff_id}"
        )],
        [InlineKeyboardButton(
            text=toggle_text,
            callback_data=f"admin_tariff_toggle_{tariff_id}"
        )],
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"admin_tariff_delete_{tariff_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin_tariffs_back"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
