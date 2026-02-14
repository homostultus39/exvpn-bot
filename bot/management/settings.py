from functools import lru_cache
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClusterConfig:
    def __init__(self, code: str, name: str, uuid: str):
        self.code = code
        self.name = name
        self.uuid = uuid


class Settings(BaseSettings):
    api_token: str
    admin_ids: str

    central_api_url: str
    central_api_username: str
    central_api_password: str

    clusters: str

    privacy_policy_url: str
    user_agreement_url: str

    payment_provider: str = "rukassa"
    rukassa_api_key: Optional[str] = None
    rukassa_shop_id: Optional[str] = None
    rukassa_api_url: Optional[str] = None

    yookassa_shop_id: Optional[str] = None
    yookassa_secret_key: Optional[str] = None

    database_path: str = "./data/bot.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @field_validator("admin_ids")
    def parse_admin_ids(cls, v: str) -> list[int]:
        return [int(x.strip()) for x in v.split(",") if x.strip()]

    @field_validator("clusters")
    def parse_clusters(cls, v: str) -> list[ClusterConfig]:
        clusters = []
        for item in v.split(","):
            parts = item.strip().split(":")
            if len(parts) == 3:
                code, name, uuid = parts
                clusters.append(ClusterConfig(code.strip(), name.strip(), uuid.strip()))
        return clusters


@lru_cache()
def get_settings() -> Settings:
    return Settings()