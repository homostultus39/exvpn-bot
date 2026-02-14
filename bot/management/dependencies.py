from functools import lru_cache
from bot.core.auth import TokenManager
from bot.core.api_client import APIClient
from bot.management.settings import get_settings


@lru_cache()
def get_token_manager() -> TokenManager:
    settings = get_settings()
    return TokenManager(
        api_url=settings.central_api_url,
        username=settings.central_api_username,
        password=settings.central_api_password
    )


def get_api_client() -> APIClient:
    settings = get_settings()
    token_manager = get_token_manager()
    return APIClient(
        base_url=settings.central_api_url,
        token_manager=token_manager
    )
