"""
Configuration

All settings are loaded from environment variables.
Copy .env.example to .env and fill in your values before running.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # Webhook Security
    # -----------------------------------------------------------------------
    # Optional shared secret. Set this in SafeSend Developer Section as the
    # API key header value, then set the same value here.
    # If blank, header validation is skipped (not recommended for production).
    WEBHOOK_SECRET: str = ""

    # -----------------------------------------------------------------------
    # Document Storage
    # -----------------------------------------------------------------------
    # Base path where downloaded documents will be saved.
    # Use a UNC path or mapped drive for network/shared storage in production.
    DOWNLOAD_BASE_PATH: str = "downloads"

    # -----------------------------------------------------------------------
    # Server
    # -----------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    # -----------------------------------------------------------------------
    # Optional downstream integrations
    # -----------------------------------------------------------------------
    # Teams webhook URL for notifications (leave blank to disable)
    TEAMS_WEBHOOK_URL: str = ""

    # Azure Service Bus connection string (leave blank to use in-memory queue)
    AZURE_SERVICE_BUS_CONNECTION_STRING: str = ""
    AZURE_SERVICE_BUS_QUEUE_NAME: str = "safesend-events"

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
