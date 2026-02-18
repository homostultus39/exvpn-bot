from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel


AppType = Literal["amnezia_vpn", "amnezia_wg"]


class CreatePeerRequest(BaseModel):
    cluster_id: UUID
    client_id: UUID
    app_type: AppType
    protocol: Optional[str] = None


class PeerResponse(BaseModel):
    id: UUID
    client_id: UUID
    cluster_id: UUID
    public_key: str
    allocated_ip: str
    endpoint: str
    app_type: str
    protocol: str
    created_at: datetime
    updated_at: datetime
    config: Optional[str] = None
    config_download_url: Optional[str] = None


class PeerWithStatsResponse(BaseModel):
    id: UUID
    client_id: UUID
    cluster_id: UUID
    public_key: str
    allocated_ip: str
    endpoint: str
    app_type: str
    protocol: str
    created_at: datetime
    updated_at: datetime
    config: Optional[str] = None
    config_download_url: Optional[str] = None
    last_handshake: Optional[datetime] = None
    rx_bytes: Optional[int] = None
    tx_bytes: Optional[int] = None
    online: Optional[bool] = None
    persistent_keepalive: Optional[int] = None
