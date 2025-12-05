"""Async MongoDB client setup using Motor."""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

# Keep a module-level client so connections are reused
_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    """Return a singleton Motor client."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Return the default database based on configuration."""
    return get_client()[settings.mongo_db]


async def get_db():
    """FastAPI dependency that yields a database handle."""
    db = get_database()
    try:
        yield db
    finally:
        # Motor uses connection pooling; explicit close not required here.
        pass

