"""Application configuration management."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    MONGO_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "smartrose"
    FM_MODEL_PATH: str = "smartrose_fm/models/fm_model.pkl"
    api_version: str = "v1"
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def mongo_uri(self) -> str:
        """Backward compatibility: lowercase alias for MONGO_URI."""
        return self.MONGO_URI

    @property
    def mongo_db(self) -> str:
        """Backward compatibility: lowercase alias for DATABASE_NAME."""
        return self.DATABASE_NAME


settings = Settings()



