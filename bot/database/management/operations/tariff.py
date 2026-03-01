from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import TariffModel


async def create_tariff(
    session: AsyncSession,
    code: str,
    name: str,
    days: int,
    price_rub: int | None,
    price_stars: int | None,
    is_active: bool = True,
    sort_order: int = 0,
) -> TariffModel:
    tariff = TariffModel(
        code=code,
        name=name,
        days=days,
        price_rub=price_rub,
        price_stars=price_stars,
        is_active=is_active,
        sort_order=sort_order,
    )
    session.add(tariff)
    await session.commit()
    await session.refresh(tariff)
    return tariff


async def get_tariff_by_id(session: AsyncSession, tariff_id: UUID) -> TariffModel | None:
    result = await session.execute(
        select(TariffModel).where(TariffModel.id == tariff_id)
    )
    return result.scalar_one_or_none()


async def update_tariff(
    session: AsyncSession,
    tariff_id: UUID,
    **kwargs,
) -> TariffModel | None:
    tariff = await get_tariff_by_id(session, tariff_id)
    if tariff is None:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(tariff, key):
            setattr(tariff, key, value)

    session.add(tariff)
    await session.commit()
    await session.refresh(tariff)
    return tariff


async def delete_tariff(session: AsyncSession, tariff_id: UUID) -> bool:
    tariff = await get_tariff_by_id(session, tariff_id)
    if tariff is None:
        return False

    await session.delete(tariff)
    await session.commit()
    return True
