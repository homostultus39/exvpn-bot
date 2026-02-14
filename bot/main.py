import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.management.settings import get_settings
from bot.routers.start import router as start_router
from bot.routers.locations import router as locations_router
from bot.routers.subscription import router as subscription_router
from bot.routers.profile import router as profile_router
from bot.routers.admin.main import router as admin_main_router
from bot.routers.admin.clusters import router as admin_clusters_router
from bot.routers.admin.statistics import router as admin_statistics_router
from bot.utils.logger import logger

settings = get_settings()

bot = Bot(
    token=settings.api_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


async def start_polling():
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(locations_router)
    dp.include_router(subscription_router)
    dp.include_router(profile_router)

    dp.include_router(admin_main_router)
    dp.include_router(admin_clusters_router)
    dp.include_router(admin_statistics_router)

    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_polling())