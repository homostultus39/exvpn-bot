from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import PromoCodeModel, PromoCodeUsageModel


async def create_promocode(
    session: AsyncSession,
    code: str,
    days: int,
    max_uses: int,
    expires_at: datetime | None = None,
) -> PromoCodeModel:
    promo = PromoCodeModel(
        code=code.strip().upper(),
        days=days,
        max_uses=max_uses,
        used_count=0,
        expires_at=expires_at,
    )
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return promo


async def get_promocode_by_code(session: AsyncSession, code: str) -> PromoCodeModel | None:
    result = await session.execute(
        select(PromoCodeModel).where(PromoCodeModel.code == code.strip().upper())
    )
    return result.scalar_one_or_none()


async def get_promocode_by_id(session: AsyncSession, promo_id: UUID) -> PromoCodeModel | None:
    result = await session.execute(
        select(PromoCodeModel).where(PromoCodeModel.id == promo_id)
    )
    return result.scalar_one_or_none()


async def list_promocodes(session: AsyncSession) -> list[PromoCodeModel]:
    result = await session.execute(
        select(PromoCodeModel).order_by(PromoCodeModel.created_at.desc())
    )
    return result.scalars().all()


async def delete_promocode(session: AsyncSession, code: str) -> bool:
    promo = await get_promocode_by_code(session, code)
    if promo is None:
        return False

    await session.delete(promo)
    await session.commit()
    return True


async def use_promocode(session: AsyncSession, code: str, user_id: int) -> dict | None:
    promo = await get_promocode_by_code(session, code)
    if promo is None:
        return None

    if promo.expires_at and datetime.now(promo.expires_at.tzinfo) > promo.expires_at:
        return None

    if promo.max_uses > 0 and promo.used_count >= promo.max_uses:
        return None

    existing_usage = await session.execute(
        select(PromoCodeUsageModel).where(
            (PromoCodeUsageModel.promo_code_id == promo.id)
            & (PromoCodeUsageModel.user_id == user_id)
        )
    )
    if existing_usage.scalar_one_or_none() is not None:
        return {"error": "already_used", "code": promo.code}

    usage = PromoCodeUsageModel(
        promo_code_id=promo.id,
        user_id=user_id,
    )
    session.add(usage)
    promo.used_count += 1
    session.add(promo)
    await session.commit()
    await session.refresh(promo)

    remaining = promo.max_uses - promo.used_count if promo.max_uses > 0 else -1
    return {"days": promo.days, "code": promo.code, "remaining": remaining}
