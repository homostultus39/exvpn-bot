from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class CreateClusterRequest(BaseModel):
    name: str
    endpoint: str
    api_key: str


class UpdateClusterRequest(BaseModel):
    name: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


class ClusterResponse(BaseModel):
    id: UUID
    name: str
    endpoint: str
    is_active: bool
    last_handshake: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ClusterWithStatusResponse(BaseModel):
    id: UUID
    name: str
    endpoint: str
    is_active: bool
    last_handshake: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    container_status: Optional[str] = None
    container_name: Optional[str] = None
    protocol: Optional[str] = None
    peers_count: int = 0
    online_peers_count: int = 0


class RestartClusterResponse(BaseModel):
    cluster_id: UUID
    status: str
    message: str
