from aiogram import Bot
from aiogram.fsm.context import FSMContext


async def cancel_active_fsm(state: FSMContext, bot: Bot) -> None:
    """Cancel any active FSM operation and delete its prompt message."""
    current_state = await state.get_state()
    if current_state is None:
        return
    data = await state.get_data()
    if "prompt_msg_id" in data and "prompt_chat_id" in data:
        try:
            await bot.delete_message(data["prompt_chat_id"], data["prompt_msg_id"])
        except Exception:
            pass
    await state.clear()
