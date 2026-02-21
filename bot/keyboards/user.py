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
        [KeyboardButton(text="🚨 Сообщение об ошибке")]
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


def get_payment_method_keyboard(
    tariff_code: str,
    price_rub: int,
    price_stars: int,
    is_extension: bool,
) -> InlineKeyboardMarkup:
    prefix = "extend" if is_extension else "buy"
    back_cb = "extend_subscription" if is_extension else "back_to_tariffs"
    buttons = [
        [InlineKeyboardButton(
            text=f"⭐ Telegram Stars ({price_stars} ⭐)",
            callback_data=f"pay_stars_{tariff_code}_{prefix}"
        )],
        [InlineKeyboardButton(
            text=f"🔵 Rukassa ({price_rub} ₽)",
            callback_data=f"pay_rukassa_{tariff_code}_{prefix}"
        )],
        [InlineKeyboardButton(
            text=f"💳 YooMoney ({price_rub} ₽)",
            callback_data=f"pay_yookassa_{tariff_code}_{prefix}"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_check_payment_keyboard(method: str, identifier: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="✅ Я оплатил",
            callback_data=f"check_{method}_{identifier}"
        )],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")
    ]])


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
