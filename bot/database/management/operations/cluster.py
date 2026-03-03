from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ClusterModel, PeerModel
from bot.management.password import encrypt_password


def _validate_cluster_mode(
    is_whitelist_gateway: bool, region_code: str | None
) -> tuple[bool, str | None]:
    if is_whitelist_gateway:
        return True, None
    if region_code is None or not region_code.strip():
        raise ValueError("Для стандартного кластера укажите непустой region_code.")
    return False, region_code


async def get_or_create_cluster(
    session: AsyncSession,
    public_name: str,
    endpoint: str,
    username: str,
    password: str,
    is_whitelist_gateway: bool = False,
    region_code: str | None = None,
) -> ClusterModel:
    normalized_is_whitelist, normalized_region_code = _validate_cluster_mode(
        is_whitelist_gateway=is_whitelist_gateway,
        region_code=region_code,
    )
    result = await session.execute(
        select(ClusterModel).where(ClusterModel.public_name == public_name)
    )
    cluster = result.scalar_one_or_none()
    if cluster:
        return cluster

    cluster = ClusterModel(
        public_name=public_name,
        endpoint=endpoint,
        username=username,
        is_whitelist_gateway=normalized_is_whitelist,
        region_code=normalized_region_code,
        encrypted_password=encrypt_password(password),
    )
    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)
    return cluster


async def get_cluster_by_id(session: AsyncSession, cluster_id: UUID) -> ClusterModel | None:
    result = await session.execute(
        select(ClusterModel).where(ClusterModel.id == cluster_id)
    )
    return result.scalar_one_or_none()


async def get_all_clusters(session: AsyncSession) -> list[ClusterModel]:
    result = await session.execute(
        select(ClusterModel).order_by(ClusterModel.public_name)
    )
    return result.scalars().all()


async def get_standard_clusters(session: AsyncSession) -> list[ClusterModel]:
    result = await session.execute(
        select(ClusterModel)
        .where(ClusterModel.is_whitelist_gateway.is_(False))
        .order_by(ClusterModel.public_name)
    )
    return result.scalars().all()


async def get_whitelist_cluster(session: AsyncSession) -> ClusterModel | None:
    result = await session.execute(
        select(ClusterModel)
        .where(ClusterModel.is_whitelist_gateway.is_(True))
        .order_by(ClusterModel.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_clusters_peers_count(session: AsyncSession, cluster_id: UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(PeerModel).where(PeerModel.cluster_id == cluster_id)
    )
    return int(result.scalar_one_or_none() or 0)


async def delete_cluster(session: AsyncSession, cluster_id: UUID) -> bool:
    cluster = await get_cluster_by_id(session, cluster_id)
    if cluster:
        await session.delete(cluster)
        await session.commit()
        return True
    return False


async def update_cluster(
    session: AsyncSession,
    cluster_id: UUID,
    public_name: str | None = None,
    endpoint: str | None = None,
    username: str | None = None,
    password: str | None = None,
    is_whitelist_gateway: bool | None = None,
    region_code: str | None = None,
    force_update_region_code: bool = False,
) -> ClusterModel | None:
    cluster = await get_cluster_by_id(session, cluster_id)
    if not cluster:
        return None

    next_is_whitelist = (
        is_whitelist_gateway if is_whitelist_gateway is not None else cluster.is_whitelist_gateway
    )
    if force_update_region_code:
        next_region = region_code
    elif region_code is not None:
        next_region = region_code
    else:
        next_region = cluster.region_code
    normalized_is_whitelist, normalized_region_code = _validate_cluster_mode(
        is_whitelist_gateway=next_is_whitelist,
        region_code=next_region,
    )
    if public_name is not None:
        cluster.public_name = public_name
    if endpoint is not None:
        cluster.endpoint = endpoint
    if username is not None:
        cluster.username = username
    if password is not None:
        cluster.encrypted_password = encrypt_password(password)
    cluster.is_whitelist_gateway = normalized_is_whitelist
    if force_update_region_code or region_code is not None or normalized_is_whitelist:
        cluster.region_code = normalized_region_code

    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)
    return cluster