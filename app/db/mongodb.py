"""Async MongoDB client setup using Motor.

This module centralizes Mongo lifecycle management so startup/shutdown hooks in
FastAPI can warm up connections, validate reachability, and close cleanly. The
global client is reused to benefit from Motor's pooling.
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Keep a module-level client so connections are reused
_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    """Return the cached Motor client, creating it if needed."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Return the default database handle."""
    return get_client()[settings.mongo_db]


async def init_db() -> None:
    """Initialize the client and validate connectivity with a ping."""
    client = get_client()
    try:
        await client.admin.command({"ping": 1})
        logger.info(
            "MongoDB ping succeeded", extra={"mongo_uri": settings.mongo_uri}
        )
    except Exception as exc:  # noqa: BLE001
        error_msg = (
            f"MongoDB connection failed: {settings.mongo_uri}\n"
            f"Error: {type(exc).__name__}: {str(exc)}\n\n"
            "To start MongoDB:\n"
            "  - Using Homebrew: brew services start mongodb-community\n"
            "  - Using Docker: cd docker && docker-compose up -d mongo\n"
            "  - Directly: mongod --dbpath /path/to/data\n"
            "  - Or use MongoDB Atlas cloud connection string in MONGO_URI"
        )
        logger.error(error_msg)
        raise ConnectionError(error_msg) from exc


async def close_db() -> None:
    """Close the MongoDB client cleanly on shutdown."""
    global _client
    if _client is not None:
        _client.close()
        logger.info("MongoDB client closed")
        _client = None


async def get_db():
    """FastAPI dependency that yields a database handle."""
    db = get_database()
    try:
        yield db
    finally:
        # Motor uses connection pooling; explicit close not required here.
        pass

