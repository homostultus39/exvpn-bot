from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import get_clients_keyboard

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.message(F.text == "👥 Клиенты")
async def clients_menu_handler(message: Message):
    await message.answer(
        "👥 <b>Управление клиентами</b>\n\n"
        "Выберите действие:",
        reply_markup=get_clients_keyboard()
    )


@router.callback_query(F.data == "admin_clients_refresh")
async def clients_refresh_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "👥 <b>Управление клиентами</b>\n\n"
        "Выберите действие:",
        reply_markup=get_clients_keyboard()
    )
    await callback.answer("Обновлено")
