"""Application configuration management."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load variables from a local .env file if present
load_dotenv()


class Settings(BaseSettings):
    """Centralized settings pulled from environment variables."""

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "smartrose"
    api_version: str = "v1"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cache settings to avoid re-reading environment values."""
    return Settings()


# Expose a singleton-style settings instance for easy imports
settings = get_settings()

