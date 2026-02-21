import time
import uuid as uuidlib
from yookassa import Configuration, Payment
from bot.management.settings import get_settings
from bot.management.logger import configure_logger

logger = configure_logger("YOOKASSA", "cyan")


def _configure() -> None:
    s = get_settings()
    Configuration.account_id = s.yookassa_shop_id
    Configuration.secret_key = s.yookassa_secret_key


async def create_payment(
    telegram_id: int,
    amount: int,
    tariff_code: str,
    tariff_name: str,
    is_extension: bool,
    return_url: str,
) -> dict:
    _configure()
    order_id = f"vpn_{telegram_id}_{int(time.time())}"
    action = "extend" if is_extension else "buy"
    idempotence_key = str(uuidlib.uuid4())

    try:
        payment = Payment.create(
            {
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": f"ExVPN — {tariff_name}",
                "metadata": {
                    "tariff_code": tariff_code,
                    "action": action,
                    "telegram_id": telegram_id,
                    "order_id": order_id,
                },
                "receipt": {
                    "customer": {"email": f"{telegram_id}@telegram.user"},
                    "items": [
                        {
                            "description": f"ExVPN подписка — {tariff_name}",
                            "quantity": "1.00",
                            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                            "vat_code": 1,
                            "payment_mode": "full_prepayment",
                            "payment_subject": "service",
                        }
                    ],
                },
            },
            idempotence_key,
        )

        logger.info(f"YooMoney payment created: {payment.id}")
        return {
            "success": True,
            "url": payment.confirmation.confirmation_url,
            "payment_id": payment.id,
            "order_id": order_id,
        }

    except Exception as e:
        logger.error(f"YooMoney create_payment exception: {e}")
        return {"success": False, "error": str(e)}


async def check_payment(payment_id: str) -> dict:
    _configure()
    try:
        payment = Payment.find_one(payment_id)
        logger.info(f"YooMoney check {payment_id}: {payment.status}")

        if payment.status == "succeeded":
            return {"status": "PAID"}
        if payment.status == "canceled":
            return {"status": "FAILED"}
        return {"status": "PENDING"}

    except Exception as e:
        logger.error(f"YooMoney check_payment exception: {e}")
        return {"status": "ERROR", "error": str(e)}
