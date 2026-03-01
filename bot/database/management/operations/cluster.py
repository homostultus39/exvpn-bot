from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ClusterModel
from bot.management.password import encrypt_password


async def get_or_create_cluster(
    session: AsyncSession,
    public_name: str,
    endpoint: str,
    username: str,
    password: str,
) -> ClusterModel:
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


async def get_clusters_peers_count(session: AsyncSession, cluster_id: UUID) -> int:
    cluster = await get_cluster_by_id(session, cluster_id)
    if cluster:
        return len(cluster.peers)
    return 0


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
) -> ClusterModel | None:
    cluster = await get_cluster_by_id(session, cluster_id)
    if not cluster:
        return None

    if public_name is not None:
        cluster.public_name = public_name
    if endpoint is not None:
        cluster.endpoint = endpoint
    if username is not None:
        cluster.username = username
    if password is not None:
        cluster.encrypted_password = encrypt_password(password)

    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)
    return cluster