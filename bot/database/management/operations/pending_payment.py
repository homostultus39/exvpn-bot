from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import PendingPaymentModel


async def create_pending_payment(
    session: AsyncSession,
    telegram_id: int,
    tariff_code: str,
    is_extension: bool,
    payment_method: str,
    amount: int,
    order_id: str | None = None,
    payment_id: str | None = None,
) -> PendingPaymentModel:
    record = PendingPaymentModel(
        telegram_id=telegram_id,
        tariff_code=tariff_code,
        is_extension=is_extension,
        payment_method=payment_method,
        amount=amount,
        order_id=order_id,
        payment_id=payment_id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_pending_by_order_id(
    session: AsyncSession, order_id: str
) -> PendingPaymentModel | None:
    result = await session.execute(
        select(PendingPaymentModel).where(PendingPaymentModel.order_id == order_id)
    )
    return result.scalar_one_or_none()


async def get_pending_by_payment_id(
    session: AsyncSession, payment_id: str
) -> PendingPaymentModel | None:
    result = await session.execute(
        select(PendingPaymentModel).where(PendingPaymentModel.payment_id == payment_id)
    )
    return result.scalar_one_or_none()


async def delete_pending_payment(session: AsyncSession, record_id) -> None:
    await session.execute(
        delete(PendingPaymentModel).where(PendingPaymentModel.id == record_id)
    )
    await session.commit()
