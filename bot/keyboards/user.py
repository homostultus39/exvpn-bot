from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.management.settings import Settings
from bot.database.management.operations.tariffs import get_all_tariffs
from bot.database.connection import get_session

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
        [KeyboardButton(text="🎟 Ввести промокод")],
        [KeyboardButton(text="🚨 Сообщение об ошибке")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_locations_keyboard(clusters: list) -> InlineKeyboardMarkup:
    buttons = []
    for cluster in clusters:
        buttons.append([
            InlineKeyboardButton(
                text=cluster.public_name,
                callback_data=f"key_loc:{cluster.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_key_mode_keyboard(cluster_id: str, region_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VPN (+WARP)", callback_data=f"key_mode:standard:{cluster_id}")],
        [InlineKeyboardButton(text="Белые списки", callback_data=f"key_mode:whitelist:{cluster_id}:{region_code}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_locations")],
    ])


async def get_subscription_keyboard(is_extension: bool = False) -> InlineKeyboardMarkup:
    prefix = "extend_" if is_extension else "buy_"
    buttons = []
    async with get_session() as session:
        tariffs = await get_all_tariffs(session)

    for tariff in tariffs:
        if tariff.code == "trial":
            buttons.append([
                InlineKeyboardButton(
                text=tariff.name,
                callback_data=tariff.code
            )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                text=f"{tariff.name} ({tariff.price_stars} ⭐ / {tariff.price_rub} ₽)",
                callback_data=f"{prefix}{tariff.code}"
                )
            ])
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
            text="🎁 Реферальная программа",
            callback_data="referral"
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


def get_error_report_cancel_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}_cancel")
    ]])
