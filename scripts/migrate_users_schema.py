"""Migrate existing users to the new schema (full_name, role, status, updated_at, is_active)."""

import asyncio
import os
import sys
from datetime import datetime

# Add parent to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient

# Use same config as app
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "smartrose")


async def migrate():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]
    coll = db.users

    cursor = coll.find({})
    updated = 0
    async for doc in cursor:
        updates = {}
        if "name" in doc and "full_name" not in doc:
            updates["full_name"] = doc["name"]
        if "roles" in doc and "role" not in doc:
            roles = doc.get("roles") or []
            updates["role"] = roles[0] if roles else "farmer"
        if "status" not in doc:
            updates["status"] = "approved"  # Existing users get approved
        if "updated_at" not in doc:
            updates["updated_at"] = doc.get("created_at") or datetime.utcnow()
        if "is_active" not in doc:
            updates["is_active"] = True

        if updates:
            await coll.update_one({"_id": doc["_id"]}, {"$set": updates})
            updated += 1
            print(f"Migrated user: {doc.get('email', doc['_id'])}")

    print(f"Migration complete. Updated {updated} users.")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
