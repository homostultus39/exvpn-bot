import asyncio
from alembic import command
from alembic.config import Config
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from bot.database.management.default.trial import seed_trial_subscription
from bot.management.settings import get_settings
from bot.scheduler.subscription_expiry import create_subscription_expiry_scheduler
from bot.routers.start import router as start_router
from bot.routers.keys import router as keys_router
from bot.routers.subscription import router as subscription_router
from bot.routers.profile import router as profile_router
from bot.routers.error_report import router as error_report_router
from bot.routers.admin.main import router as admin_main_router
from bot.routers.admin.clusters import router as admin_clusters_router
from bot.routers.admin.clients import router as admin_clients_router
from bot.routers.admin.statistics import router as admin_statistics_router
from bot.routers.admin.tariffs import router as admin_tariffs_router
from bot.routers.admin.broadcast import router as admin_broadcast_router
from bot.routers.admin.support import router as admin_support_router
from bot.middlewares.fsm_cancel import FsmCancelOnMenuMiddleware
from bot.database.management.default.admins import seed_admins
from bot.management.logger import configure_logger

settings = get_settings()
logger = configure_logger("EXVPN_BOT", "blue")


def run_migrations() -> None:
    logger.info("Running database migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations applied successfully.")

bot = Bot(
    token=settings.api_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


async def setup_commands() -> None:
    user_commands = [
        BotCommand(command="start", description="Запустить бота"),
    ]
    admin_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="admin", description="Открыть админ-панель"),
    ]

    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logger.warning(f"Could not set commands for admin {admin_id}: {e}")


async def start_polling():
    run_migrations()
    await seed_admins()
    await seed_trial_subscription()
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.outer_middleware(FsmCancelOnMenuMiddleware())

    dp.include_router(start_router)
    dp.include_router(keys_router)
    dp.include_router(subscription_router)
    dp.include_router(profile_router)
    dp.include_router(error_report_router)

    dp.include_router(admin_main_router)
    dp.include_router(admin_clusters_router)
    dp.include_router(admin_clients_router)
    dp.include_router(admin_statistics_router)
    dp.include_router(admin_tariffs_router)
    dp.include_router(admin_broadcast_router)
    dp.include_router(admin_support_router)

    logger.info("Bot starting...")
    await setup_commands()
    logger.info(settings.api_token)
    subscription_scheduler = create_subscription_expiry_scheduler()
    subscription_scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        subscription_scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(start_polling())
