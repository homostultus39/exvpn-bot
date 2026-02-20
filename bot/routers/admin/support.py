import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from bot.database.connection import sessionmaker
from bot.database.management.operations.report import get_oldest_unanswered, set_reply
from bot.management.fsm_utils import cancel_active_fsm
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import get_admin_menu_keyboard, get_support_ticket_keyboard, get_support_cancel_keyboard
from bot.management.logger import configure_logger

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
logger = configure_logger("ADMIN_SUPPORT", "red")


class SupportReplyForm(StatesGroup):
    waiting_for_reply = State()


async def _show_next_ticket(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    skip_ids: list[uuid.UUID] | None = None
) -> None:
    async with sessionmaker() as session:
        ticket = await get_oldest_unanswered(session, skip_ids=skip_ids)

    if ticket is None:
        await bot.send_message(chat_id, "✅ <b>Новых обращений нет.</b>\n\nНажмите «📋 Обращения» чтобы проверить снова.")
        await state.clear()
        return

    msg = await bot.send_message(
        chat_id,
        f"📩 <b>Обращение от пользователя</b> <code>{ticket.user_id}</code>\n"
        f"🕐 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"{ticket.message}",
        reply_markup=get_support_ticket_keyboard()
    )

    current_skip_ids = skip_ids or []
    await state.update_data(
        ticket_id=str(ticket.id),
        ticket_user_id=ticket.user_id,
        ticket_msg_id=msg.message_id,
        ticket_chat_id=chat_id,
        skip_ids=[str(s) for s in current_skip_ids]
    )


@router.message(F.text == "📋 Обращения")
async def support_list_handler(message: Message, state: FSMContext, bot: Bot):
    await cancel_active_fsm(state, bot)
    try:
        await message.delete()
    except Exception:
        pass
    await _show_next_ticket(bot, message.chat.id, state)


@router.callback_query(F.data == "support_reply")
async def support_reply_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportReplyForm.waiting_for_reply)
    await callback.message.edit_reply_markup(reply_markup=get_support_cancel_keyboard())
    await callback.answer()


@router.callback_query(StateFilter(SupportReplyForm), F.data == "support_cancel")
async def support_reply_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Ответ отменён.", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "support_cancel")
async def support_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "support_skip")
async def support_skip(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    old_skip_ids_str: list[str] = data.get("skip_ids", [])

    await callback.message.delete()
    await callback.answer()

    new_skip_ids_str = old_skip_ids_str + ([ticket_id] if ticket_id else [])
    new_skip_ids = [uuid.UUID(s) for s in new_skip_ids_str]

    await _show_next_ticket(bot, callback.message.chat.id, state, skip_ids=new_skip_ids)


@router.message(SupportReplyForm.waiting_for_reply)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot):
    reply_text = message.text
    data = await state.get_data()

    ticket_id = uuid.UUID(data["ticket_id"])
    ticket_user_id: int = data["ticket_user_id"]
    ticket_msg_id: int = data["ticket_msg_id"]
    ticket_chat_id: int = data["ticket_chat_id"]

    try:
        await message.delete()
    except Exception:
        pass

    try:
        async with sessionmaker() as session:
            await set_reply(session, ticket_id=ticket_id, reply=reply_text)

        try:
            await bot.delete_message(ticket_chat_id, ticket_msg_id)
        except Exception:
            pass

        await bot.send_message(
            ticket_user_id,
            f"💬 <b>Ответ на ваше обращение:</b>\n\n{reply_text}"
        )

        await message.answer(
            "✅ <b>Ответ доставлен пользователю.</b>\n\n"
            "Нажмите «📋 Обращения» чтобы получить следующее обращение.",
            reply_markup=get_admin_menu_keyboard()
        )
        logger.info(f"Admin {message.from_user.id} replied to ticket {ticket_id} for user {ticket_user_id}")

    except Exception as e:
        logger.error(f"Error sending reply for ticket {ticket_id}: {e}")
        await message.answer(
            f"❌ Ошибка при отправке ответа:\n\n<code>{str(e)}</code>",
            reply_markup=get_admin_menu_keyboard()
        )

    await state.clear()
