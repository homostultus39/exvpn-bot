from uuid import UUID
from bot.entities.cluster.repository import ClusterRepository
from bot.entities.cluster.models import ClusterWithStatusResponse
from bot.management.settings import Settings, ClusterConfig


class ClusterService:
    def __init__(self, repository: ClusterRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    async def get_cluster(self, cluster_id: UUID) -> ClusterWithStatusResponse:
        return await self.repository.get(cluster_id)

    async def list_clusters(self) -> list[ClusterWithStatusResponse]:
        return await self.repository.list()

    async def get_active_clusters(self) -> list[ClusterWithStatusResponse]:
        clusters = await self.repository.list()
        return [cluster for cluster in clusters if cluster.is_active]

    def get_configured_clusters(self) -> list[ClusterConfig]:
        return self.settings.clusters

    async def get_cluster_by_code(self, code: str) -> ClusterWithStatusResponse | None:
        configured = next((c for c in self.settings.clusters if c.code == code), None)
        if not configured:
            return None

        try:
            cluster_uuid = UUID(configured.uuid)
            return await self.repository.get(cluster_uuid)
        except Exception:
            return None

    async def restart_cluster(self, cluster_id: UUID):
        return await self.repository.restart(cluster_id)
