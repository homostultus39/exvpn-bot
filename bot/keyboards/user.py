from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.management.settings import Settings
from bot.entities.cluster.models import ClusterWithStatusResponse
from bot.entities.tariff.models import TariffResponse


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


def get_location_keyboard(clusters: list[ClusterWithStatusResponse]) -> InlineKeyboardMarkup:
    buttons = []
    for cluster in clusters:
        buttons.append([InlineKeyboardButton(
            text=cluster.name,
            callback_data=f"loc:{cluster.id}"
        )])
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="back_to_menu"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_app_type_keyboard(cluster_id: str, cluster_name: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="AmneziaVPN",
            callback_data=f"key:{cluster_id}:amnezia_vpn"
        )],
        [InlineKeyboardButton(
            text="AmneziaWG",
            callback_data=f"key:{cluster_id}:amnezia_wg"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_locations"
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_subscription_keyboard(tariffs: list[TariffResponse], is_extension: bool = False) -> InlineKeyboardMarkup:
    prefix = "extend_" if is_extension else "buy_"
    buttons = []
    for tariff in tariffs:
        buttons.append([InlineKeyboardButton(
            text=f"{tariff.name} ({tariff.price_stars} ⭐ / {tariff.price_rub} ₽)",
            callback_data=f"{prefix}{tariff.code}"
        )])
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="back_to_menu"
    )])
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
