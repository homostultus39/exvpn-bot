from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    username: str
    is_admin: bool = False


class UpdateClientRequest(BaseModel):
    expires_at: datetime


class SubscribeRequest(BaseModel):
    tariff_code: str


class ClientResponse(BaseModel):
    id: UUID
    username: str
    expires_at: datetime | None
    subscription_status: str
    trial_used: bool
    is_admin: bool = False
    last_subscription_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClientWithPeersResponse(BaseModel):
    id: UUID
    username: str
    expires_at: datetime | None
    subscription_status: str
    trial_used: bool
    is_admin: bool = False
    last_subscription_at: datetime | None
    created_at: datetime
    updated_at: datetime
    peers_count: int = 0
