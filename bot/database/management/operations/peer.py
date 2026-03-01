from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.xray_panel_client import XrayPanelClient
from bot.database.models import ClusterModel, PeerModel


async def get_peer_by_user_and_cluster(
    session: AsyncSession, user_db_id: UUID, cluster_id: UUID
) -> PeerModel | None:
    result = await session.execute(
        select(PeerModel).where(
            (PeerModel.client_id == user_db_id) & (PeerModel.cluster_id == cluster_id)
        )
    )
    return result.scalar_one_or_none()


async def get_peers_by_user(session: AsyncSession, user_db_id: UUID) -> list[PeerModel]:
    result = await session.execute(
        select(PeerModel).where(PeerModel.client_id == user_db_id)
    )
    return list(result.scalars().all())


async def create_peer(
    session: AsyncSession, client_id: UUID, cluster_id: UUID, url: str
) -> PeerModel:
    peer = PeerModel(client_id=client_id, cluster_id=cluster_id, url=url)
    session.add(peer)
    await session.commit()
    await session.refresh(peer)
    return peer


async def delete_peers_by_user(session: AsyncSession, user_db_id: UUID) -> int:
    result = await session.execute(
        delete(PeerModel).where(PeerModel.client_id == user_db_id)
    )
    await session.commit()
    return int(result.rowcount or 0)


async def get_or_create_peer_for_cluster(
    session: AsyncSession,
    user_db_id: UUID,
    user_id: int,
    cluster: ClusterModel,
    xray_client: XrayPanelClient,
    expires_at: datetime | None,
) -> PeerModel:
    existing_peer = await get_peer_by_user_and_cluster(session, user_db_id, cluster.id)
    if existing_peer:
        current_url = await xray_client.get_connection_url(user_id=user_id)
        if current_url is not None:
            if existing_peer.url != current_url:
                existing_peer.url = current_url
                session.add(existing_peer)
                await session.commit()
                await session.refresh(existing_peer)
            return existing_peer
        await session.delete(existing_peer)
        await session.commit()

    key_url = await xray_client.add_client(user_id=user_id, expires_at=expires_at)
    return await create_peer(
        session=session,
        client_id=user_db_id,
        cluster_id=cluster.id,
        url=key_url,
    )
