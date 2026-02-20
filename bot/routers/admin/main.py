from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.middlewares.admin import AdminMiddleware
from bot.management.fsm_utils import cancel_active_fsm
from bot.keyboards.admin import get_admin_menu_keyboard
from bot.keyboards.user import get_main_menu_keyboard
from bot.messages.admin import ADMIN_MENU

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.message(Command("admin"))
async def admin_menu_handler(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    await message.answer(
        ADMIN_MENU,
        reply_markup=get_admin_menu_keyboard()
    )


@router.message(F.text == "◀️ Выход из админ-панели")
async def exit_admin_handler(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    await message.answer(
        "👋 Вы вышли из админ-панели",
        reply_markup=get_main_menu_keyboard()
    )
