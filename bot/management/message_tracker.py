from aiogram import Bot

_last_messages: dict[int, int] = {}  # {chat_id: message_id}


def store(chat_id: int, message_id: int) -> None:
    _last_messages[chat_id] = message_id


def get(chat_id: int) -> int | None:
    return _last_messages.get(chat_id)


def clear(chat_id: int) -> None:
    _last_messages.pop(chat_id, None)


async def delete_last(bot: Bot, chat_id: int) -> None:
    prev_id = get(chat_id)
    if prev_id:
        try:
            await bot.delete_message(chat_id, prev_id)
        except Exception:
            pass
        clear(chat_id)
