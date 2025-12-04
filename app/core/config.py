from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List


class Settings(BaseSettings):
    """
    Application settings
    """
    # App settings
    APP_NAME: str = "SmartRose Backend"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./smartrose.db"
    
    # API settings
    API_V1_PREFIX: str = "/api/v1"
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()


