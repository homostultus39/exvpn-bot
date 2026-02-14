from uuid import UUID
from bot.core.api_client import APIClient
from bot.entities.peer.models import (
    CreatePeerRequest,
    UpdatePeerRequest,
    PeerResponse,
    PeerWithStatsResponse
)


class PeerRepository:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    async def create(self, request: CreatePeerRequest) -> PeerResponse:
        data = await self.api_client.post("/peers/", json=request.model_dump(mode="json"))
        return PeerResponse(**data)

    async def get(self, peer_id: UUID) -> PeerResponse:
        data = await self.api_client.get(f"/peers/{peer_id}")
        return PeerResponse(**data)

    async def list(self) -> list[PeerResponse]:
        data = await self.api_client.get("/peers/")
        return [PeerResponse(**item) for item in data]

    async def update(self, peer_id: UUID, request: UpdatePeerRequest) -> PeerResponse:
        data = await self.api_client.patch(f"/peers/{peer_id}", json=request.model_dump(mode="json", exclude_none=True))
        return PeerResponse(**data)

    async def delete(self, peer_id: UUID) -> None:
        await self.api_client.delete(f"/peers/{peer_id}")

    async def get_statistics(self, peer_id: UUID) -> PeerWithStatsResponse:
        data = await self.api_client.get(f"/peers/{peer_id}/statistics")
        return PeerWithStatsResponse(**data)

    async def find_by_client_and_cluster(self, client_id: UUID, cluster_id: UUID) -> PeerResponse | None:
        peers = await self.list()
        for peer in peers:
            if peer.client_id == client_id and peer.cluster_id == cluster_id:
                return peer
        return None
