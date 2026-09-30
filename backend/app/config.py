from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://parking:parking@db:5432/parking"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 720

    initial_owner_username: str = "owner"
    initial_owner_password: str = "owner1234"
    seed_demo_data: bool = True
    demo_password: str = "demo1234"
    # Enables /api/demo (backend trace, time fast-forward, data reset). Turn off in production.
    demo_mode: bool = True

    timezone: str = "Asia/Bangkok"
    log_level: str = "INFO"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
