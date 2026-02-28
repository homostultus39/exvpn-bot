import pytz
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import UserModel, SubscriptionStatus
from bot.database.management.operations.tariffs import get_tariff_by_code
from bot.management.settings import get_settings


async def get_admin_by_user_id(session: AsyncSession, user_id: int) -> UserModel | None:
    result = await session.execute(
        select(UserModel).where(UserModel.user_id == user_id and UserModel.is_admin)
    )
    return result.scalar_one_or_none()

async def get_all_admin_ids(session: AsyncSession) -> list:
    result = await session.execute(
        select(UserModel).where(UserModel.is_admin)
    )
    return result.scalars().all()

async def create_admin(session: AsyncSession, user_id: int) -> UserModel:
    admin = UserModel(
        user_id=user_id,
        aggreed_to_terms=True,
        subscription_status=SubscriptionStatus.UNLIMITED.value,
        is_admin=True
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin

async def get_user_by_user_id(session: AsyncSession, user_id: int) -> UserModel | None:
    result = await session.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    return result.scalar_one_or_none()

async def get_or_create_user_record(session: AsyncSession, user_id: int) -> UserModel:
    existing_user = await get_user_by_user_id(session, user_id)

    if existing_user:
        return existing_user
    
    user = UserModel(
        user_id=user_id
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def make_terms_confirmed(session: AsyncSession, user_id: int) -> None:
    selected_user = await get_user_by_user_id(session, user_id)
    selected_user.aggreed_to_terms = True
    session.add(selected_user)
    await session.commit()

async def update_user_subscription(session: AsyncSession, user_id: int, tariff_code: str) -> None:
    selected_user = await get_user_by_user_id(session, user_id)
    tariff = await get_tariff_by_code(session, tariff_code)
    
    selected_user.subscription_status = SubscriptionStatus.ACTIVE.value if tariff_code != "trial" else SubscriptionStatus.TRIAL.value
    if tariff_code == "trial":
        selected_user.trial_used = True

    tz = pytz.timezone(get_settings().timezone)
    if selected_user.expires_at and selected_user.expires_at > datetime.now(tz):
        selected_user.expires_at = selected_user.expires_at + timedelta(days=tariff.days)
    else:
        selected_user.expires_at = datetime.now(tz) + timedelta(days=tariff.days)

    session.add(selected_user)
    await session.commit()

async def is_trial_used(session: AsyncSession, user_id: int) -> bool:
    selected_user = await get_user_by_user_id(session, user_id)
    return selected_user.trial_used