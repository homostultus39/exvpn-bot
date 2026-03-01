from functools import lru_cache
from pydantic import field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_token: str
    admin_ids: str
    timezone: str = "UTC"
    trial_period_days: int = 3
    password_encryption_key: str = ""

    privacy_policy_url: str
    user_agreement_url: str

    yookassa_shop_id: str
    yookassa_secret_key: str

    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @field_validator("admin_ids")
    def parse_admin_ids(cls, v: str) -> list[int]:
        return [int(x.strip()) for x in v.split(",") if x.strip()]

    @computed_field
    @property
    def async_postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @computed_field
    @property
    def sync_postgres_url(self) -> str:
        return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
