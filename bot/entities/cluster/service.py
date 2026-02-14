from uuid import UUID
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.models import (
    ClusterWithStatusResponse,
    CreateClusterRequest,
    ClusterResponse
)


class ClusterService:
    def __init__(self, repository: ClusterRepository):
        self.repository = repository

    async def get_cluster(self, cluster_id: UUID) -> ClusterWithStatusResponse:
        return await self.repository.get(cluster_id)

    async def list_clusters(self) -> list[ClusterWithStatusResponse]:
        return await self.repository.list()

    async def get_active_clusters(self) -> list[ClusterWithStatusResponse]:
        clusters = await self.repository.list()
        return [cluster for cluster in clusters if cluster.is_active]

    async def create_cluster(
        self,
        name: str,
        endpoint: str,
        api_key: str
    ) -> ClusterResponse:
        request = CreateClusterRequest(
            name=name,
            endpoint=endpoint,
            api_key=api_key
        )
        return await self.repository.create(request)

    async def restart_cluster(self, cluster_id: UUID):
        return await self.repository.restart(cluster_id)
