from typing import Optional
from uuid import UUID
from bot.core.api_client import APIClient
from bot.entities.client.models import (
    CreateClientRequest,
    UpdateClientRequest,
    ClientResponse,
    ClientWithPeersResponse
)


class ClientRepository:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    async def create(self, request: CreateClientRequest) -> ClientResponse:
        data = await self.api_client.post("/clients/", json=request.model_dump(mode="json"))
        return ClientResponse(**data)

    async def get(self, client_id: UUID) -> ClientWithPeersResponse:
        data = await self.api_client.get(f"/clients/{client_id}")
        return ClientWithPeersResponse(**data)

    async def list(self) -> list[ClientWithPeersResponse]:
        data = await self.api_client.get("/clients/")
        return [ClientWithPeersResponse(**item) for item in data]

    async def update(self, client_id: UUID, request: UpdateClientRequest) -> ClientResponse:
        data = await self.api_client.patch(f"/clients/{client_id}", json=request.model_dump(mode="json"))
        return ClientResponse(**data)

    async def delete(self, client_id: UUID) -> None:
        await self.api_client.delete(f"/clients/{client_id}")

    async def find_by_username(self, username: str) -> Optional[ClientWithPeersResponse]:
        clients = await self.list()
        for client in clients:
            if client.username == username:
                return client
        return None
