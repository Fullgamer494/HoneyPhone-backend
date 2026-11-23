from pathlib import Path

from pydantic import Field
from pydantic import model_validator
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
    auth_secret_key: str = "local-only-change-this-secret-before-deploying"
    google_client_ids: str = ""
    aws_region: str = "us-east-2"
    email_from: str = "noreply@myuspot.org"
    public_base_url: str = "https://honeyphone-api.myuspot.org"
    apk_download_url: str = ""

    @model_validator(mode="after")
    def production_secret_is_not_default(self):
        if self.app_env.lower() == "production" and (len(self.auth_secret_key) < 32 or "local-only" in self.auth_secret_key):
            raise ValueError("AUTH_SECRET_KEY must be a random secret of at least 32 characters in production.")
        return self

    @property
    def google_audiences(self) -> list[str]:
        return [value.strip() for value in self.google_client_ids.split(",") if value.strip()]


settings = Settings()
