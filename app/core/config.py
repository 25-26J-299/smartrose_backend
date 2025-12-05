"""Application configuration management."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load variables from a local .env file if present
load_dotenv()


class Settings(BaseSettings):
    """Centralized settings pulled from environment variables."""

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "smartrose"
    api_version: str = "v1"

    # Allow unknown env vars (extra="ignore") so deployment envs with
    # additional variables don't break startup. Keep case-insensitive to match
    # common env naming patterns.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cache settings to avoid re-reading environment values."""
    return Settings()


# Expose a singleton-style settings instance for easy imports
settings = get_settings()

