from bot.database.connection import sessionmaker
from bot.database.management.operations.telegram_admin import get_admin_by_user_id, create_admin
from bot.management.settings import get_settings
from bot.management.logger import configure_logger

logger = configure_logger("DB_DEFAULTS", "cyan")


async def seed_admins() -> None:
    """Create DB records for admin IDs listed in settings if they don't exist yet."""
    settings = get_settings()
    async with sessionmaker() as session:
        for user_id in settings.admin_ids:
            existing = await get_admin_by_user_id(session, user_id)
            if not existing:
                await create_admin(session, user_id)
                logger.info(f"Created admin record for user_id={user_id}")
