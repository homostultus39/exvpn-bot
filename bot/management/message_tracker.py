"""
In-memory tracker for "main" bot messages per chat.
Supports multiple message IDs per user — all are deleted together on navigation.
State is lost on bot restart (acceptable for UX purposes).
"""

from aiogram import Bot

_last_messages: dict[int, list[int]] = {}  # {chat_id: [message_ids]}


def store(chat_id: int, *message_ids: int) -> None:
    _last_messages[chat_id] = list(message_ids)


def get(chat_id: int) -> list[int]:
    return _last_messages.get(chat_id, [])


def clear(chat_id: int) -> None:
    _last_messages.pop(chat_id, None)


async def delete_last(bot: Bot, chat_id: int) -> None:
    """Delete all previously tracked bot messages for this chat."""
    ids = _last_messages.pop(chat_id, [])
    for msg_id in ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
