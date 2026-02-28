import asyncio
import hashlib
import hmac
from alembic import command
from alembic.config import Config
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiohttp import web

from bot.database.management.default.trial import seed_trial_subscription
from bot.database.management.operations.user import update_user_subscription
from bot.management.settings import get_settings
from bot.routers.start import router as start_router
# from bot.routers.locations import router as locations_router
from bot.routers.subscription import router as subscription_router
# from bot.routers.profile import router as profile_router
from bot.routers.error_report import router as error_report_router
# from bot.routers.admin.main import router as admin_main_router
# from bot.routers.admin.clusters import router as admin_clusters_router
# from bot.routers.admin.cluster_create import router as admin_cluster_create_router
# from bot.routers.admin.clients import router as admin_clients_router
# from bot.routers.admin.client_register import router as admin_client_register_router
# from bot.routers.admin.statistics import router as admin_statistics_router
# from bot.routers.admin.tariffs import router as admin_tariffs_router
# from bot.routers.admin.broadcast import router as admin_broadcast_router
# from bot.routers.admin.support import router as admin_support_router
from bot.middlewares.fsm_cancel import FsmCancelOnMenuMiddleware
from bot.database.management.default.admins import seed_admins
from bot.database.management.operations.pending_payment import (
    get_pending_by_order_id,
    delete_pending_payment,
)
from bot.database.connection import get_session, sessionmaker
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


async def rukassa_webhook(request: web.Request) -> web.Response:
    try:
        data = await request.post()
        payment_id = data.get("id", "")
        order_id = data.get("order_id", "")
        status = data.get("status", "")
        amount = data.get("amount", "0")
        in_amount = data.get("in_amount", "0")
        created = data.get("createdDateTime", "")
        signature = data.get("sign", "")

        expected_sign = hmac.new(
            settings.rukassa_api_key.encode(),
            f"{payment_id}|{created}|{amount}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if signature != expected_sign:
            logger.warning(f"Rukassa webhook: invalid signature for order {order_id}")
            return web.Response(text="ERROR SIGN")

        if float(in_amount) < float(amount):
            logger.warning(f"Rukassa webhook: insufficient amount for order {order_id}")
            return web.Response(text="ERROR AMOUNT")

        if status == "PAID":
            async with sessionmaker() as session:
                pending = await get_pending_by_order_id(session, order_id)
                if not pending:
                    logger.warning(f"Rukassa webhook: pending not found for order {order_id}")
                    return web.Response(text="OK")

                user_id = pending.user_id
                tariff_code = pending.tariff_code
                record_id = pending.id
                async with get_session() as session:
                    await update_user_subscription(session, user_id, tariff_code)

            async with get_session() as session:
                await delete_pending_payment(session, record_id)

            await bot.send_message(
                chat_id=user_id,
                text="✅ <b>Оплата через Rukassa подтверждена!</b>\n\n"
                     "Подписка активирована. Используйте кнопку <b>🔑 Получить ключ</b>.",
            )
            logger.info(f"Rukassa webhook: subscription activated for user {user_id}, order {order_id}")

        return web.Response(text="OK")

    except Exception as e:
        logger.error(f"Rukassa webhook error: {e}")
        return web.Response(text="ERROR")


async def start_webhook_server() -> None:
    app = web.Application()
    app.router.add_post("/rukassa/webhook", rukassa_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Rukassa webhook server started on :8080")


async def start_polling():
    run_migrations()
    await seed_admins()
    await seed_trial_subscription()
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.outer_middleware(FsmCancelOnMenuMiddleware())

    dp.include_router(start_router)
    # dp.include_router(locations_router)
    dp.include_router(subscription_router)
    # dp.include_router(profile_router)
    dp.include_router(error_report_router)

    # dp.include_router(admin_main_router)
    # dp.include_router(admin_clusters_router)
    # dp.include_router(admin_cluster_create_router)
    # dp.include_router(admin_clients_router)
    # dp.include_router(admin_client_register_router)
    # dp.include_router(admin_statistics_router)
    # dp.include_router(admin_tariffs_router)
    # dp.include_router(admin_broadcast_router)
    # dp.include_router(admin_support_router)

    logger.info("Bot starting...")
    await setup_commands()
    logger.info(settings.api_token)
    # asyncio.create_task(start_webhook_server())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_polling())
