import pytz
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.xray_panel_client import XrayPanelClient
from bot.database.management.operations.cluster import get_cluster_by_id
from bot.database.management.operations.peer import (
    delete_peers_by_user,
    get_peers_by_user,
)
from bot.database.models import UserModel, SubscriptionStatus
from bot.database.management.operations.tariffs import get_tariff_by_code
from bot.management.settings import get_settings


async def get_admin_by_user_id(session: AsyncSession, user_id: int) -> UserModel | None:
    result = await session.execute(
        select(UserModel).where((UserModel.user_id == user_id) & (UserModel.is_admin))
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


async def register_user_by_admin(
    session: AsyncSession,
    user_id: int,
    is_admin: bool,
    expires_at: datetime | None = None,
) -> UserModel:
    if not is_admin and expires_at is None:
        raise ValueError("expires_at is required for non-admin users")

    subscription_status = (
        SubscriptionStatus.UNLIMITED.value if is_admin else SubscriptionStatus.ACTIVE.value
    )
    normalized_expires_at = None if is_admin else expires_at

    selected_user = await get_user_by_user_id(session, user_id)
    if selected_user:
        selected_user.is_admin = is_admin
        selected_user.expires_at = normalized_expires_at
        selected_user.subscription_status = subscription_status
        selected_user.aggreed_to_terms = False
        session.add(selected_user)
        await session.commit()
        await session.refresh(selected_user)
        return selected_user

    user = UserModel(
        user_id=user_id,
        is_admin=is_admin,
        expires_at=normalized_expires_at,
        subscription_status=subscription_status,
        aggreed_to_terms=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def update_user_subscription(session: AsyncSession, user_id: int, tariff_code: str) -> None:
    selected_user = await get_user_by_user_id(session, user_id)
    if selected_user and selected_user.is_admin:
        return

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

async def get_all_user_ids(session: AsyncSession) -> list:
    result = await session.execute(
        select(UserModel.user_id)
    )
    return list(result.scalars().all())


async def is_subscription_active(session: AsyncSession, user_id: int) -> bool:
    selected_user = await get_user_by_user_id(session, user_id)
    if selected_user is None:
        return False
    if selected_user.subscription_status == SubscriptionStatus.UNLIMITED.value:
        return True
    if selected_user.expires_at is None:
        return False

    tz = pytz.timezone(get_settings().timezone)
    return selected_user.expires_at > datetime.now(tz)


async def expire_outdated_subscriptions(session: AsyncSession) -> int:
    tz = pytz.timezone(get_settings().timezone)
    now = datetime.now(tz)
    result = await session.execute(
        select(UserModel).where(
            (UserModel.expires_at.is_not(None))
            & (UserModel.expires_at < now)
            & (
                (UserModel.subscription_status == SubscriptionStatus.ACTIVE.value)
                | (UserModel.subscription_status == SubscriptionStatus.TRIAL.value)
            )
        )
    )
    users = list(result.scalars().all())
    for user in users:
        peers = await get_peers_by_user(session, user.id)
        for peer in peers:
            cluster = await get_cluster_by_id(session, peer.cluster_id)
            if cluster is None:
                continue
            xray_client = XrayPanelClient.from_cluster(cluster)
            await xray_client.delete_client(user.user_id)
        await delete_peers_by_user(session, user.id)
        user.subscription_status = SubscriptionStatus.EXPIRED.value
        session.add(user)
    await session.commit()
    return len(users)