from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import TelegramAdminModel


async def get_admin_by_user_id(session: AsyncSession, user_id: int) -> TelegramAdminModel | None:
    result = await session.execute(
        select(TelegramAdminModel).where(TelegramAdminModel.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_admin(session: AsyncSession, user_id: int) -> TelegramAdminModel:
    admin = TelegramAdminModel(user_id=user_id)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def sync_admins_from_settings(session: AsyncSession, admin_ids: list[int]) -> None:
    """Create records for admin IDs from settings that don't exist yet."""
    for user_id in admin_ids:
        existing = await get_admin_by_user_id(session, user_id)
        if not existing:
            await create_admin(session, user_id)
