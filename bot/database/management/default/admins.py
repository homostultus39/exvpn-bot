from bot.database.connection import sessionmaker
from bot.database.management.operations.user import get_admin_by_user_id, create_admin
from bot.management.settings import get_settings
from bot.database.management.default.logger import logger


async def seed_admins() -> None:
    settings = get_settings()
    async with sessionmaker() as session:
        for user_id in settings.admin_ids:
            existing = await get_admin_by_user_id(session, user_id)
            if not existing:
                await create_admin(session, user_id)
                logger.info(f"Created admin record for user_id={user_id}")
