from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from bot.database.connection import get_session
from bot.database.management.operations.user import get_all_user_ids
from bot.middlewares.fsm_cancel import cancel_active_fsm
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import (
    get_admin_menu_keyboard,
    get_broadcast_cancel_keyboard,
    get_broadcast_confirm_keyboard,
)
from bot.management.logger import configure_logger

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_BROADCAST", "red")


class BroadcastForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_confirm = State()


@router.message(F.text == "📢 Рассылка")
async def broadcast_start(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    msg = await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Введите текст для рассылки всем пользователям:",
        reply_markup=get_broadcast_cancel_keyboard()
    )
    await state.update_data(prompt_msg_id=msg.message_id, prompt_chat_id=msg.chat.id)
    await state.set_state(BroadcastForm.waiting_for_text)


@router.callback_query(StateFilter(BroadcastForm), F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Рассылка отменена.", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.message(BroadcastForm.waiting_for_text)
async def broadcast_text_received(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(broadcast_text=message.text)
    data = await state.get_data()
    await message.delete()

    try:
        await bot.edit_message_text(
            chat_id=data["prompt_chat_id"],
            message_id=data["prompt_msg_id"],
            text=f"📢 <b>Предпросмотр рассылки:</b>\n\n{message.text}\n\n"
                 f"Подтвердите отправку всем пользователям:",
            reply_markup=get_broadcast_confirm_keyboard()
        )
    except Exception:
        pass

    await state.set_state(BroadcastForm.waiting_for_confirm)


@router.callback_query(BroadcastForm.waiting_for_confirm, F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    await callback.message.edit_text("⏳ Выполняю рассылку...", reply_markup=None)
    await callback.answer()

    try:
        async with get_session() as session:
            users = await get_all_user_ids(session)

        sent = 0
        failed = 0
        for user_id in users:
            try:
                await bot.send_message(user_id, text)
                sent += 1
            except Exception:
                failed += 1

        await callback.message.edit_text(
            f"✅ <b>Рассылка завершена</b>\n\n"
            f"📨 Отправлено: {sent}\n"
            f"❌ Не доставлено: {failed}"
        )
        logger.info(f"Broadcast by admin {callback.from_user.id}: sent={sent}, failed={failed}")

    except Exception as e:
        logger.error(f"Error in broadcast_confirm: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при рассылке:\n\n<code>{str(e)}</code>"
        )
