"""Data access helpers for the sensor_readings collection."""

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "sensor_readings"


async def insert_sensor_reading(db: AsyncIOMotorDatabase, payload: dict) -> str:
    """Insert a reading and return the inserted document id."""
    result = await db[COLLECTION_NAME].insert_one(payload)
    return str(result.inserted_id)

