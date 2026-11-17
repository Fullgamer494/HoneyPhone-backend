from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://honeyphone_dev:honeyphone_local_only@127.0.0.1:5433/honeyphone"
    max_body_bytes: int = Field(default=65536, ge=65536, le=65536)


settings = Settings()
