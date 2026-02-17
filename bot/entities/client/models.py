from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    username: str


class UpdateClientRequest(BaseModel):
    expires_at: datetime


class SubscribeRequest(BaseModel):
    tariff_code: str


class ClientResponse(BaseModel):
    id: UUID
    username: str
    expires_at: datetime
    subscription_status: str
    trial_used: bool
    last_subscription_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClientWithPeersResponse(BaseModel):
    id: UUID
    username: str
    expires_at: datetime
    subscription_status: str
    trial_used: bool
    last_subscription_at: datetime | None
    created_at: datetime
    updated_at: datetime
    peers_count: int = 0
