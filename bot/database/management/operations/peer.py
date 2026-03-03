from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.xray_panel_client import XrayPanelClient
from bot.database.models import ClusterModel, PeerModel
from bot.management.logger import configure_logger

logger = configure_logger("PEER_OPERATIONS", "magenta")


def _build_client_email(user_id: int, key_type: str, region_code: str) -> str:
    normalized_region = region_code.lower()
    if key_type == "whitelist":
        return f"{user_id}_wl_{normalized_region}"
    return f"{user_id}_{normalized_region}"


async def get_peer_by_user_cluster_key_type_region(
    session: AsyncSession,
    user_db_id: UUID,
    cluster_id: UUID,
    key_type: str,
    region_code: str,
) -> PeerModel | None:
    result = await session.execute(
        select(PeerModel).where(
            (PeerModel.client_id == user_db_id)
            & (PeerModel.cluster_id == cluster_id)
            & (PeerModel.key_type == key_type)
            & (PeerModel.region_code == region_code)
        )
    )
    return result.scalar_one_or_none()


async def get_peers_by_user(session: AsyncSession, user_db_id: UUID) -> list[PeerModel]:
    result = await session.execute(
        select(PeerModel).where(PeerModel.client_id == user_db_id).order_by(PeerModel.created_at)
    )
    return list(result.scalars().all())


async def create_peer(
    session: AsyncSession,
    client_id: UUID,
    cluster_id: UUID,
    url: str,
    key_type: str,
    region_code: str,
    client_email: str,
) -> PeerModel:
    peer = PeerModel(
        client_id=client_id,
        cluster_id=cluster_id,
        url=url,
        key_type=key_type,
        region_code=region_code,
        client_email=client_email,
    )
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


async def _find_legacy_peer(
    session: AsyncSession,
    user_db_id: UUID,
    cluster_id: UUID,
    key_type: str,
) -> PeerModel | None:
    result = await session.execute(
        select(PeerModel)
        .where(
            (PeerModel.client_id == user_db_id)
            & (PeerModel.cluster_id == cluster_id)
            & (PeerModel.key_type == key_type)
            & (PeerModel.region_code == "")
        )
        .order_by(PeerModel.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _update_peer_fields(
    session: AsyncSession,
    peer: PeerModel,
    url: str,
    client_email: str,
    region_code: str,
) -> PeerModel:
    changed = False

    if peer.url != url:
        peer.url = url
        changed = True

    if peer.client_email != client_email:
        peer.client_email = client_email
        changed = True

    if peer.region_code != region_code:
        peer.region_code = region_code
        changed = True

    if changed:
        session.add(peer)
        await session.commit()
        await session.refresh(peer)
        logger.info(
            f"Updated peer {peer.id}: region={region_code}, email={client_email}"
        )

    return peer


async def get_or_create_peer_for_cluster(
    session: AsyncSession,
    user_db_id: UUID,
    user_id: int,
    cluster: ClusterModel,
    xray_client: XrayPanelClient,
    expires_at: datetime | None,
    key_type: str,
    region_code: str,
) -> PeerModel:
    normalized_region = region_code.lower()
    expected_client_email = _build_client_email(user_id, key_type, normalized_region)

    logger.info(
        f"Getting peer for user={user_id}, cluster={cluster.id}, "
        f"key_type={key_type}, region={normalized_region}, email={expected_client_email}"
    )

    existing_peer = await get_peer_by_user_cluster_key_type_region(
        session=session,
        user_db_id=user_db_id,
        cluster_id=cluster.id,
        key_type=key_type,
        region_code=normalized_region,
    )

    if existing_peer is None:
        existing_peer = await _find_legacy_peer(
            session=session,
            user_db_id=user_db_id,
            cluster_id=cluster.id,
            key_type=key_type,
        )
        if existing_peer:
            logger.info(
                f"Found legacy peer {existing_peer.id} with empty region_code, "
                f"will migrate to region={normalized_region}"
            )

    if existing_peer:
        logger.info(
            f"Found existing peer {existing_peer.id}: "
            f"region={existing_peer.region_code}, email={existing_peer.client_email}"
        )

        current_url = await xray_client.get_connection_url(client_email=expected_client_email)

        if current_url is not None:
            logger.info(f"Client {expected_client_email} exists on panel, updating peer")
            return await _update_peer_fields(
                session=session,
                peer=existing_peer,
                url=current_url,
                client_email=expected_client_email,
                region_code=normalized_region,
            )

        logger.warning(
            f"Client {expected_client_email} not found on panel, "
            f"deleting peer {existing_peer.id} and creating new client"
        )
        await session.delete(existing_peer)
        await session.commit()

    logger.info(f"Creating new client {expected_client_email} on panel")
    key_url = await xray_client.add_client(
        user_id=user_id,
        expires_at=expires_at,
        client_email=expected_client_email,
    )

    new_peer = await create_peer(
        session=session,
        client_id=user_db_id,
        cluster_id=cluster.id,
        url=key_url,
        key_type=key_type,
        region_code=normalized_region,
        client_email=expected_client_email,
    )

    logger.info(f"Created new peer {new_peer.id} for region={normalized_region}")
    return new_peer
