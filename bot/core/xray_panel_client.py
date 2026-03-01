import uuid
from datetime import datetime

from py3xui import AsyncApi, Client

from bot.database.models import ClusterModel
from bot.management.password import decrypt_password


def _normalize_endpoint(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"http://{value}"


class XrayPanelClient:
    def __init__(self, endpoint: str, username: str, password: str):
        self.endpoint = _normalize_endpoint(endpoint)
        self.api = AsyncApi(self.endpoint, username, password)
        self._is_logged_in = False

    @classmethod
    def from_cluster(cls, cluster: ClusterModel) -> "XrayPanelClient":
        return cls(
            endpoint=cluster.endpoint,
            username=cluster.username,
            password=decrypt_password(cluster.encrypted_password),
        )

    async def _login(self) -> None:
        if not self._is_logged_in:
            await self.api.login()
            self._is_logged_in = True

    @staticmethod
    def _is_client_not_found_error(error: Exception) -> bool:
        message = str(error).lower()
        return "inbound not found for email" in message

    async def get_client_by_email(self, user_id: int) -> Client | None:
        await self._login()
        email = str(user_id)
        try:
            return await self.api.client.get_by_email(email)
        except Exception as error:
            if self._is_client_not_found_error(error):
                return None
            raise

    @staticmethod
    def _expiry_ms(expires_at: datetime | None) -> int:
        if expires_at is None:
            return 0
        return int(expires_at.timestamp() * 1000)

    @staticmethod
    def _build_connection_url(endpoint: str, client_id: str, user_id: int) -> str:
        host = endpoint.removeprefix("http://").removeprefix("https://")
        return f"vless://{client_id}@{host}?security=none#{user_id}"

    async def get_inbounds_list(self):
        await self._login()
        return await self.api.inbound.get_list()

    async def add_client(self, user_id: int, expires_at: datetime | None) -> str:
        await self._login()
        inbounds = await self.api.inbound.get_list()
        if not inbounds:
            raise ValueError("No inbounds found on cluster")

        inbound = inbounds[0]
        email = str(user_id)
        existing = await self.get_client_by_email(user_id)
        if existing:
            return self._build_connection_url(self.endpoint, str(existing.id), user_id)

        client_id = str(uuid.uuid4())
        client = Client(
            id=client_id,
            email=email,
            enable=True,
            expiry_time=self._expiry_ms(expires_at),
            total_gb=0,
            limit_ip=0,
        )
        await self.api.client.add(inbound.id, [client])
        return self._build_connection_url(self.endpoint, client_id, user_id)

    async def delete_client(self, user_id: int) -> None:
        existing = await self.get_client_by_email(user_id)
        if existing:
            await self.api.client.delete(existing.id)

    async def update_client(self, user_id: int, expires_at: datetime | None) -> None:
        existing = await self.get_client_by_email(user_id)
        if not existing:
            return
        existing.expiry_time = self._expiry_ms(expires_at)
        await self.api.client.update(existing.id, existing)

    async def get_cluster_stats(self) -> dict:
        await self._login()
        inbounds = await self.api.inbound.get_list()

        total_clients = 0
        total_online = 0
        total_rx = 0
        total_tx = 0

        for inbound in inbounds:
            clients = getattr(inbound.settings, "clients", []) if getattr(inbound, "settings", None) else []
            total_clients += len(clients)
            total_online += len([client for client in clients if getattr(client, "enable", False)])
            total_rx += getattr(inbound, "up", 0) or 0
            total_tx += getattr(inbound, "down", 0) or 0

        return {
            "inbounds_total": len(inbounds),
            "clients_total": total_clients,
            "clients_online": total_online,
            "rx_bytes": total_rx,
            "tx_bytes": total_tx,
        }
