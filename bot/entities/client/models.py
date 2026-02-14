from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    username: str
    expires_at: datetime


class UpdateClientRequest(BaseModel):
    expires_at: datetime


class ClientResponse(BaseModel):
    id: UUID
    username: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ClientWithPeersResponse(BaseModel):
    id: UUID
    username: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    peers_count: int = 0
