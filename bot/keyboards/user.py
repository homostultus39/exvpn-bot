from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.management.settings import Settings, ClusterConfig


def get_agreement_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="📋 Политика конфиденциальности",
            url=settings.privacy_policy_url
        )],
        [InlineKeyboardButton(
            text="📄 Пользовательское соглашение",
            url=settings.user_agreement_url
        )],
        [InlineKeyboardButton(
            text="✅ Согласен",
            callback_data="agree_to_terms"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🔑 Получить ключ")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💎 Подписка")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_location_keyboard(clusters: list[ClusterConfig]) -> InlineKeyboardMarkup:
    buttons = []
    for cluster in clusters:
        buttons.append([InlineKeyboardButton(
            text=cluster.name,
            callback_data=f"location_{cluster.code}"
        )])
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="back_to_menu"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_subscription_keyboard(is_extension: bool = False) -> InlineKeyboardMarkup:
    prefix = "extend_" if is_extension else "buy_"
    buttons = [
        [InlineKeyboardButton(
            text="1 месяц (48 ⭐ / 90 RUB)",
            callback_data=f"{prefix}30"
        )],
        [InlineKeyboardButton(
            text="3 месяца (136 ⭐ / 256 RUB)",
            callback_data=f"{prefix}90"
        )],
        [InlineKeyboardButton(
            text="6 месяцев (266 ⭐ / 502 RUB)",
            callback_data=f"{prefix}180"
        )],
        [InlineKeyboardButton(
            text="1 год (515 ⭐ / 972 RUB)",
            callback_data=f"{prefix}360"
        )],
        [InlineKeyboardButton(
            text="🧪 Тестовая подписка (для дебага)",
            callback_data=f"{prefix}test"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_menu"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_profile_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="💎 Продлить подписку",
            callback_data="extend_subscription"
        )],
        [InlineKeyboardButton(
            text="🔑 Мои ключи",
            callback_data="my_keys"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_menu"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
