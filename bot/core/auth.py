import asyncio
from datetime import datetime, timedelta
from bot.management.timezone import now as get_now
from typing import Optional
import httpx
from bot.core.exceptions import AuthenticationException


class TokenManager:
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def get_access_token(self) -> str:
        async with self._lock:
            if self.access_token and self.token_expires_at:
                if get_now() < self.token_expires_at - timedelta(minutes=1):
                    return self.access_token

            if self.refresh_token:
                try:
                    await self._refresh_tokens()
                    return self.access_token
                except Exception:
                    pass

            await self._login()
            return self.access_token

    async def _login(self) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/auth/login",
                json={"username": self.username, "password": self.password}
            )

            if response.status_code != 200:
                raise AuthenticationException(
                    f"Login failed: {response.text}",
                    response.status_code
                )

            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = response.cookies.get("refresh_token")
            self.token_expires_at = get_now() + timedelta(minutes=15)

    async def _refresh_tokens(self) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/auth/refresh",
                cookies={"refresh_token": self.refresh_token}
            )

            if response.status_code != 200:
                raise AuthenticationException(
                    f"Token refresh failed: {response.text}",
                    response.status_code
                )

            data = response.json()
            self.access_token = data["access_token"]
            new_refresh = response.cookies.get("refresh_token")
            if new_refresh:
                self.refresh_token = new_refresh
            self.token_expires_at = get_now() + timedelta(minutes=15)

    async def logout(self) -> None:
        if not self.access_token:
            return

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.api_url}/auth/logout",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    cookies={"refresh_token": self.refresh_token} if self.refresh_token else {}
                )
        finally:
            self.access_token = None
            self.refresh_token = None
            self.token_expires_at = None
