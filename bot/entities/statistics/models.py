from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ClientsByStatus(BaseModel):
    active: int = 0
    trial: int = 0
    expired: int = 0


class ClientsStats(BaseModel):
    total: int
    by_status: ClientsByStatus


class ClustersStats(BaseModel):
    total: int
    active: int
    inactive: int


class PeersByAppType(BaseModel):
    amnezia_vpn: int = 0
    amnezia_wg: int = 0


class PeersStats(BaseModel):
    total: int
    online: int
    by_app_type: PeersByAppType


class TrafficStats(BaseModel):
    total_rx_bytes: Optional[int] = None
    total_tx_bytes: Optional[int] = None


class GlobalStatsResponse(BaseModel):
    clusters: ClustersStats
    clients: ClientsStats
    peers: PeersStats
    traffic: TrafficStats


class ClusterInfo(BaseModel):
    id: UUID
    name: str
    protocol: Optional[str] = None
    container_status: Optional[str] = None
    is_active: bool


class ClusterClientsStats(BaseModel):
    total: int


class ClusterStatsResponse(BaseModel):
    cluster: ClusterInfo
    clients: ClusterClientsStats
    peers: PeersStats
    traffic: TrafficStats
