from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import TariffModel


async def get_or_create_tariff(session: AsyncSession,
                        code: str,
                        name: str,
                        days: int,
                        price_rub: int | None = None,
                        price_stars: int | None = None,
                        sort_order: int = 0) -> TariffModel:
    existing = await get_tariff_by_code(session, code)
    if existing:
        return existing
    
    tariff = TariffModel(
        code=code,
        name=name,
        days=days,
        price_rub=price_rub,
        price_stars=price_stars,
        sort_order=sort_order
    )
    session.add(tariff)
    await session.commit()
    await session.refresh(tariff)
    return tariff

async def get_tariff_by_code(session: AsyncSession, code: str) -> TariffModel | None:
    result = await session.execute(
        select(TariffModel).where(TariffModel.code == code)
    )
    return result.scalar_one_or_none()

async def get_all_tariffs(session: AsyncSession) -> list[TariffModel]:
    result = await session.execute(
        select(TariffModel).order_by(TariffModel.sort_order)
    )
    return result.scalars().all()

async def is_table_empty(session: AsyncSession) -> bool:
    result = await session.execute(
        select(TariffModel).limit(1)
    )
    return result.scalar_one_or_none() is None