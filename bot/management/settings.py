from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_token: str
    admin_ids: str
    timezone: str = "UTC"

    central_api_url: str
    central_api_username: str
    central_api_password: str

    privacy_policy_url: str
    user_agreement_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @field_validator("admin_ids")
    def parse_admin_ids(cls, v: str) -> list[int]:
        return [int(x.strip()) for x in v.split(",") if x.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()