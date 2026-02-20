from uuid import UUID
from bot.core.api_client import APIClient
from bot.entities.statistics.models import GlobalStatsResponse, ClusterStatsResponse


class StatisticsRepository:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    async def get_global(self) -> GlobalStatsResponse:
        data = await self.api_client.get("/statistics/")
        return GlobalStatsResponse(**data)

    async def get_cluster(self, cluster_id: UUID) -> ClusterStatsResponse:
        data = await self.api_client.get(f"/statistics/clusters/{cluster_id}")
        return ClusterStatsResponse(**data)
