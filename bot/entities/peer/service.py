from uuid import UUID
from bot.entities.peer.repository import PeerRepository
from bot.entities.peer.models import CreatePeerRequest, PeerResponse, AppType


class PeerService:
    def __init__(self, repository: PeerRepository):
        self.repository = repository

    async def get_or_create_peer(
        self,
        client_id: UUID,
        cluster_id: UUID,
        app_type: AppType = "amnezia_wg",
        protocol: str = "wireguard"
    ) -> PeerResponse:
        existing = await self.repository.find_by_client_and_cluster(client_id, cluster_id)
        if existing:
            return existing

        request = CreatePeerRequest(
            cluster_id=cluster_id,
            client_id=client_id,
            app_type=app_type,
            protocol=protocol
        )
        return await self.repository.create(request)

    async def get_client_peers(self, client_id: UUID) -> list[PeerResponse]:
        all_peers = await self.repository.list()
        return [peer for peer in all_peers if peer.client_id == client_id]

    async def get_peer_config(self, peer_id: UUID) -> str | None:
        peer = await self.repository.get(peer_id)
        return peer.config

    async def delete_peer(self, peer_id: UUID) -> None:
        await self.repository.delete(peer_id)

    async def get_peer_statistics(self, peer_id: UUID):
        return await self.repository.get_statistics(peer_id)
