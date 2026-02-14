from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🌐 Кластеры"), KeyboardButton(text="👥 Клиенты")],
        [KeyboardButton(text="📊 Статистика")],
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
