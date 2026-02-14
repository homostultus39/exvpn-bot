import httpx
from typing import Optional, Any
from bot.core.auth import TokenManager
from bot.core.exceptions import APIException, AuthenticationException, NotFoundException, ValidationException


class APIClient:
    def __init__(self, base_url: str, token_manager: TokenManager):
        self.base_url = base_url
        self.token_manager = token_manager
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def _get_headers(self) -> dict[str, str]:
        token = await self.token_manager.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None
    ) -> Any:
        if not self._client:
            raise RuntimeError("APIClient must be used as async context manager")

        request_headers = await self._get_headers()
        if headers:
            request_headers.update(headers)

        response = await self._client.request(
            method=method,
            url=endpoint,
            json=json,
            params=params,
            headers=request_headers
        )

        if response.status_code == 401:
            raise AuthenticationException("Unauthorized", 401)
        elif response.status_code == 404:
            raise NotFoundException("Resource not found", 404)
        elif response.status_code == 422:
            raise ValidationException(f"Validation error: {response.text}", 422)
        elif response.status_code >= 400:
            raise APIException(f"API error: {response.text}", response.status_code)

        if response.status_code == 204:
            return None

        return response.json()

    async def get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json: Optional[dict] = None) -> Any:
        return await self._request("POST", endpoint, json=json)

    async def patch(self, endpoint: str, json: Optional[dict] = None) -> Any:
        return await self._request("PATCH", endpoint, json=json)

    async def delete(self, endpoint: str) -> Any:
        return await self._request("DELETE", endpoint)
