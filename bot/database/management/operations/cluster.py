from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import ClusterModel

async def get_or_create_cluster(session: AsyncSession, name: str) -> ClusterModel:
    result = await session.execute(
        select(ClusterModel).where(ClusterModel.name == name)
    )
    cluster = result.scalar_one_or_none()
    if cluster:
        return cluster
    
    cluster = ClusterModel(name=name)
    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)
    return cluster

async def get_cluster_by_id(session: AsyncSession, cluster_id: int) -> ClusterModel | None:
    result = await session.execute(
        select(ClusterModel).where(ClusterModel.id == cluster_id)
    )
    return result.scalar_one_or_none()

async def get_all_clusters(session: AsyncSession) -> list[ClusterModel]:
    result = await session.execute(
        select(ClusterModel).order_by(ClusterModel.name)
    )
    return result.scalars().all()