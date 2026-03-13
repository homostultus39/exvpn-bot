from aiogram.types import Message

from bot.keyboards.user import get_agreement_keyboard, get_main_menu_keyboard
from bot.management.message_tracker import delete_last, store
from bot.management.settings import get_settings
from bot.messages.user import CLIENT_INFO, MAIN_MENU_MESSAGE, WELCOME_MESSAGE


async def show_main_menu(message: Message, clear_tracked: bool = False) -> None:
    if clear_tracked:
        await delete_last(message.bot, message.chat.id)

    sent_info = await message.answer(CLIENT_INFO)
    sent_menu = await message.answer(
        MAIN_MENU_MESSAGE,
        reply_markup=get_main_menu_keyboard(),
    )
    store(message.chat.id, sent_info.message_id, sent_menu.message_id)


async def show_welcome_message(message: Message) -> None:
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_agreement_keyboard(get_settings()),
    )
