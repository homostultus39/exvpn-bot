from uuid import UUID
from bot.core.api_client import APIClient
from bot.entities.cluster.models import (
    CreateClusterRequest,
    UpdateClusterRequest,
    ClusterResponse,
    ClusterWithStatusResponse,
    RestartClusterResponse
)


class ClusterRepository:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    async def create(self, request: CreateClusterRequest) -> ClusterResponse:
        data = await self.api_client.post("/clusters/", json=request.model_dump(mode="json"))
        return ClusterResponse(**data)

    async def get(self, cluster_id: UUID) -> ClusterWithStatusResponse:
        data = await self.api_client.get(f"/clusters/{cluster_id}")
        return ClusterWithStatusResponse(**data)

    async def list(self) -> list[ClusterWithStatusResponse]:
        data = await self.api_client.get("/clusters/")
        return [ClusterWithStatusResponse(**item) for item in data]

    async def update(self, cluster_id: UUID, request: UpdateClusterRequest) -> ClusterResponse:
        data = await self.api_client.patch(f"/clusters/{cluster_id}", json=request.model_dump(mode="json", exclude_none=True))
        return ClusterResponse(**data)

    async def delete(self, cluster_id: UUID) -> None:
        await self.api_client.delete(f"/clusters/{cluster_id}")

    async def restart(self, cluster_id: UUID) -> RestartClusterResponse:
        data = await self.api_client.post(f"/clusters/{cluster_id}/restart")
        return RestartClusterResponse(**data)
