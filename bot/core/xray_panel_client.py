import uuid
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode, urlparse

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

    def _endpoint_host(self) -> str:
        parsed = urlparse(self.endpoint)
        if parsed.hostname:
            return parsed.hostname
        return self.endpoint.removeprefix("http://").removeprefix("https://").split(":")[0]

    @staticmethod
    def _find_client_in_inbounds(inbounds: list[Any], user_id: int) -> tuple[Any, Any] | None:
        email = str(user_id)
        for inbound in inbounds:
            settings = getattr(inbound, "settings", None)
            clients = getattr(settings, "clients", []) if settings is not None else []
            for client in clients or []:
                if str(getattr(client, "email", "")) == email:
                    return inbound, client
        return None

    def _build_connection_url(self, inbound: Any, client_id: str, user_id: int) -> str:
        protocol = str(getattr(inbound, "protocol", "vless") or "vless")
        host = self._endpoint_host()
        port = int(getattr(inbound, "port", 443) or 443)

        stream_settings = getattr(inbound, "stream_settings", None)
        network = str(getattr(stream_settings, "network", "tcp") or "tcp")
        security = str(getattr(stream_settings, "security", "none") or "none")

        params: list[tuple[str, str]] = [("type", network)]
        if protocol == "vless":
            params.append(("encryption", "none"))
        if network == "tcp" and stream_settings is not None:
            tcp_settings = getattr(stream_settings, "tcp_settings", {}) or {}
            if isinstance(tcp_settings, dict):
                header = tcp_settings.get("header") or {}
                if isinstance(header, dict):
                    header_type = header.get("type")
                    if header_type:
                        params.append(("headerType", str(header_type)))
                    path: str | None = None
                    request = header.get("request")
                    if isinstance(request, dict):
                        request_path = request.get("path")
                        if isinstance(request_path, list) and request_path:
                            path = str(request_path[0])
                        elif isinstance(request_path, str):
                            path = request_path
                    elif isinstance(header.get("path"), str):
                        path = header["path"]
                    if path:
                        params.append(("path", path))

        params.append(("security", security))
        if security == "reality" and stream_settings is not None:
            reality_settings = getattr(stream_settings, "reality_settings", {}) or {}
            if isinstance(reality_settings, dict):
                reality_inner = reality_settings.get("settings") or {}
                if not isinstance(reality_inner, dict):
                    reality_inner = {}

                public_key = reality_inner.get("publicKey") or reality_settings.get("publicKey")
                if public_key:
                    params.append(("pbk", str(public_key)))

                fingerprint = reality_inner.get("fingerprint") or reality_settings.get("fingerprint")
                if fingerprint:
                    params.append(("fp", str(fingerprint)))

                server_names = reality_settings.get("serverNames") or reality_inner.get("serverNames")
                if isinstance(server_names, list) and server_names:
                    params.append(("sni", str(server_names[0])))

                short_ids = reality_settings.get("shortIds") or reality_inner.get("shortIds")
                if isinstance(short_ids, list) and short_ids:
                    params.append(("sid", str(short_ids[0])))

                spider_x = reality_inner.get("spiderX") or reality_settings.get("spiderX")
                if isinstance(spider_x, str) and spider_x:
                    params.append(("spx", spider_x))

        fragment_label = str(getattr(inbound, "remark", "ExVPN") or "ExVPN")
        fragment = quote(f"{fragment_label}-{user_id}")
        query = urlencode(params, doseq=True, quote_via=quote)
        return f"{protocol}://{client_id}@{host}:{port}?{query}#{fragment}"

    def _get_connection_url_from_inbounds(self, inbounds: list[Any], user_id: int) -> str | None:
        found = self._find_client_in_inbounds(inbounds, user_id)
        if found is None:
            return None
        inbound, client = found
        client_id = str(getattr(client, "id", "") or "")
        if not client_id:
            return None
        return self._build_connection_url(inbound, client_id, user_id)

    async def get_inbounds_list(self):
        await self._login()
        return await self.api.inbound.get_list()

    async def get_connection_url(self, user_id: int) -> str | None:
        await self._login()
        inbounds = await self.api.inbound.get_list()
        return self._get_connection_url_from_inbounds(inbounds, user_id)

    async def add_client(self, user_id: int, expires_at: datetime | None) -> str:
        await self._login()
        inbounds = await self.api.inbound.get_list()
        if not inbounds:
            raise ValueError("No inbounds found on cluster")

        existing_url = self._get_connection_url_from_inbounds(inbounds, user_id)
        if existing_url:
            return existing_url

        inbound = inbounds[0]
        email = str(user_id)
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
        return self._build_connection_url(inbound, client_id, user_id)

    async def delete_client(self, user_id: int) -> None:
        await self._login()
        inbounds = await self.api.inbound.get_list()
        found = self._find_client_in_inbounds(inbounds, user_id)
        if found is None:
            return
        _, existing = found
        client_id = str(getattr(existing, "id", "") or "")
        if client_id:
            await self.api.client.delete(client_id)

    async def update_client(self, user_id: int, expires_at: datetime | None) -> None:
        await self._login()
        inbounds = await self.api.inbound.get_list()
        found = self._find_client_in_inbounds(inbounds, user_id)
        if found is None:
            return
        _, existing = found
        client_id = str(getattr(existing, "id", "") or "")
        if not client_id:
            return
        existing.expiry_time = self._expiry_ms(expires_at)
        await self.api.client.update(client_id, existing)

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
