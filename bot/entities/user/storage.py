import aiosqlite
from datetime import datetime
from typing import Optional
from uuid import UUID
from bot.entities.user.models import BotUser


class UserStorage:
    def __init__(self, database_path: str):
        self.database_path = database_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_users (
                    telegram_id INTEGER PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    agreed_to_terms INTEGER NOT NULL DEFAULT 0,
                    agreement_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.commit()

    async def create(self, telegram_id: int, client_id: UUID, agreed_to_terms: bool = False) -> BotUser:
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO bot_users (telegram_id, client_id, agreed_to_terms, agreement_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_id,
                    str(client_id),
                    1 if agreed_to_terms else 0,
                    now if agreed_to_terms else None,
                    now,
                    now
                )
            )
            await db.commit()

        return await self.get(telegram_id)

    async def get(self, telegram_id: int) -> Optional[BotUser]:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM bot_users WHERE telegram_id = ?",
                (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return BotUser(
                        telegram_id=row["telegram_id"],
                        client_id=UUID(row["client_id"]),
                        agreed_to_terms=bool(row["agreed_to_terms"]),
                        agreement_date=datetime.fromisoformat(row["agreement_date"]) if row["agreement_date"] else None,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
        return None

    async def update_agreement(self, telegram_id: int) -> None:
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                """
                UPDATE bot_users
                SET agreed_to_terms = 1, agreement_date = ?, updated_at = ?
                WHERE telegram_id = ?
                """,
                (now, now, telegram_id)
            )
            await db.commit()

    async def exists(self, telegram_id: int) -> bool:
        user = await self.get(telegram_id)
        return user is not None
