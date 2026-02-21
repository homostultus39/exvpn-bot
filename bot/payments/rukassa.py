import time
import json
import aiohttp
from bot.management.settings import get_settings
from bot.management.logger import configure_logger

logger = configure_logger("RUKASSA", "cyan")


async def create_payment(
    telegram_id: int,
    amount: int,
    tariff_code: str,
    is_extension: bool,
) -> dict:
    s = get_settings()
    order_id = f"vpn_{telegram_id}_{int(time.time())}"
    action = "extend" if is_extension else "buy"

    data = {
        "shop_id": int(s.rukassa_shop_id),
        "order_id": order_id,
        "amount": amount,
        "token": s.rukassa_api_key,
        "data": json.dumps({"tariff_code": tariff_code, "action": action}),
        "user_code": str(telegram_id),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{s.rukassa_api_url}/create",
                data=data,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                result = await response.json(content_type=None)

        if "error" in result:
            logger.error(f"Rukassa error: {result}")
            return {"success": False, "error": result.get("message", "Unknown error")}

        if "url" in result:
            logger.info(f"Rukassa payment created: {order_id}")
            return {"success": True, "url": result["url"], "order_id": order_id}

        return {"success": False, "error": "No payment URL in response"}

    except Exception as e:
        logger.error(f"Rukassa create_payment exception: {e}")
        return {"success": False, "error": str(e)}


async def check_payment(order_id: str) -> dict:
    s = get_settings()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{s.rukassa_api_url}/check",
                json={"shop_id": s.rukassa_shop_id, "order_id": order_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                result = await response.json(content_type=None)

        logger.info(f"Rukassa check {order_id}: {result}")
        status = result.get("status", "")
        return {"status": "PAID" if status == "PAID" else status}

    except Exception as e:
        logger.error(f"Rukassa check_payment exception: {e}")
        return {"status": "ERROR", "error": str(e)}
