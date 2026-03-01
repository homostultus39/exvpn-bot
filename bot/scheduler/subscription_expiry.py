import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot.database.connection import get_session
from bot.database.management.operations.user import expire_outdated_subscriptions
from bot.management.logger import configure_logger
from bot.management.settings import get_settings

logger = configure_logger("SUBSCRIPTION_SCHEDULER", "blue")


async def run_subscription_expiry_job() -> None:
    try:
        async with get_session() as session:
            updated = await expire_outdated_subscriptions(session)
        if updated:
            logger.info(f"Updated expired subscriptions: {updated}")
    except Exception as e:
        logger.error(f"Subscription scheduler error: {e}")


def create_subscription_expiry_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    timezone = pytz.timezone(settings.timezone)
    scheduler = AsyncIOScheduler(timezone=timezone)
    scheduler.add_job(
        run_subscription_expiry_job,
        trigger=CronTrigger(minute=0, timezone=timezone),
        id="expire_outdated_subscriptions",
        replace_existing=True,
    )
    return scheduler
