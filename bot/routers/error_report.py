from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from bot.database.connection import get_session
from bot.database.management.operations.report import create_ticket
from bot.keyboards.user import get_error_report_cancel_keyboard
from bot.management.logger import configure_logger
from bot.middlewares.terms import AcceptedTermsMiddleware

router = Router()
router.message.middleware(AcceptedTermsMiddleware())
router.callback_query.middleware(AcceptedTermsMiddleware())
logger = configure_logger("ERROR_REPORT", "yellow")

PREFIX = "er"


class ErrorReportForm(StatesGroup):
    waiting_for_message = State()


@router.message(F.text == "🚨 Сообщение об ошибке")
async def error_report_start(message: Message, state: FSMContext, bot: Bot):
    try:
        await message.delete()
    except Exception:
        pass

    msg = await message.answer(
        "🚨 <b>Сообщение об ошибке</b>\n\n"
        "Опишите вашу проблему или ошибку, и мы постараемся помочь вам как можно скорее.\n\n"
        "Введите текст сообщения:",
        reply_markup=get_error_report_cancel_keyboard(PREFIX)
    )
    await state.update_data(prompt_msg_id=msg.message_id, prompt_chat_id=msg.chat.id)
    await state.set_state(ErrorReportForm.waiting_for_message)


@router.callback_query(StateFilter(ErrorReportForm), F.data == f"{PREFIX}_cancel")
async def error_report_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.message(ErrorReportForm.waiting_for_message)
async def error_report_message(message: Message, state: FSMContext, bot: Bot):
    text = message.text
    user_id = message.from_user.id
    data = await state.get_data()

    try:
        await message.delete()
    except Exception:
        pass

    try:
        async with get_session() as session:
            await create_ticket(session, user_id=user_id, message=text)

        await bot.edit_message_text(
            chat_id=data["prompt_chat_id"],
            message_id=data["prompt_msg_id"],
            text="✅ <b>Сообщение получено!</b>\n\n"
                 "Мы ответим вам в ближайшее время.\n"
                 "Следите за сообщениями от бота.",
        )
        logger.info(f"User {user_id} submitted error report: {text[:50]!r}")
    except Exception as e:
        logger.error(f"Error saving ticket from user {user_id}: {e}")
        try:
            await bot.edit_message_text(
                chat_id=data["prompt_chat_id"],
                message_id=data["prompt_msg_id"],
                text="❌ Не удалось отправить сообщение. Попробуйте позже.",
            )
        except Exception:
            pass

    await state.clear()
