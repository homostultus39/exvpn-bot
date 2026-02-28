from bot.database.connection import get_session
from bot.database.management.operations.tariffs import get_or_create_tariff
from bot.management.settings import get_settings
from bot.database.management.default.logger import logger


async def seed_trial_subscription() -> None:
    settings = get_settings()
    async with get_session() as session:
        await get_or_create_tariff(session, "trial", "🎁 Пробный период", settings.trial_period_days)
        logger.info("Trial subscription seeded successfully")
