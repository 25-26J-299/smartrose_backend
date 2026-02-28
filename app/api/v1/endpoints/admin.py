"""Admin-only endpoints for user and location (greenhouse/flower shop) management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import devices as device_repo
from app.db.collections import locations as location_repo
from app.db.collections import users as user_repo
from app.db.mongodb import get_db
from app.models.device_models import DeviceCreate, DeviceUpdate
from app.models.user_models import (
    LocationUpdate,
    RoleUpdate,
    StatusUpdate,
    UserPublic,
    UserUpdate,
)
from app.services.auth_service import decode_jwt

router = APIRouter()
bearer_scheme = HTTPBearer()


def _public_user(document: dict) -> dict:
    """Convert a stored user document to a public schema."""
    doc = dict(document)
    doc.setdefault("full_name", doc.get("name", ""))
    doc.setdefault("role", (doc.get("roles") or ["farmer"])[0])
    doc.setdefault("status", "pending")
    doc.setdefault("is_active", True)
    return UserPublic(**doc).model_dump(by_alias=True)


async def _get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Validate JWT and return user only if they have admin role."""
    token = credentials.credentials
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user = await user_repo.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    role = user.get("role") or (user.get("roles") or [""])[0]
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


@router.get("/search", summary="Search approved users and locations (admin)")
async def search_for_device_assignment(
    q: str = Query(..., min_length=2, description="Search by email, phone, or location name"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Search approved users by email, phone, full_name, or by location name.
    Returns users with their locations for device assignment."""
    # 1. Search users by email, phone, full_name
    users_by_profile = await user_repo.search_approved_users(db, q)
    user_ids_from_profile = {u["_id"] for u in users_by_profile}

    # 2. Search locations by name, get user_ids
    locations_matching = await location_repo.search_locations_by_name(db, q)
    user_ids_from_locations = {loc["user_id"] for loc in locations_matching}

    # 3. Merge user IDs
    all_user_ids = list(user_ids_from_profile | user_ids_from_locations)
    if not all_user_ids:
        return {"results": []}

    # 4. Get full user data for all (ensure approved)
    users = await user_repo.get_users_by_ids(db, all_user_ids)
    user_map = {u["_id"]: u for u in users}

    # 5. Build results: user + their locations
    results = []
    for user in users:
        locs = await location_repo.get_locations_by_user(db, user["_id"])
        results.append({
            "user": _public_user(user),
            "locations": locs,
        })
    return {"results": results}


@router.get("/users", summary="List all users (admin)")
async def list_users(
    status: str | None = Query(None, description="Filter by status: approved, pending, rejected"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return all users. Excludes password_hash. Optional status filter."""
    users = await user_repo.get_all_users(db, status_filter=status)
    return {"users": [_public_user(u) for u in users]}


@router.get("/users/{user_id}", summary="Get user with locations (admin)")
async def get_user_with_locations(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return user details and their locations for review."""
    user = await user_repo.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    locations = await location_repo.get_locations_by_user(db, user_id)
    return {
        "user": _public_user(user),
        "locations": locations,
    }


@router.patch("/users/{user_id}", summary="Update user (admin)")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Update user full_name, phone, or role."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        user = await user_repo.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return {"user": _public_user(user)}
    updated = await user_repo.update_user(
        db,
        user_id,
        full_name=updates.get("full_name"),
        phone=updates.get("phone"),
        role=updates.get("role"),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"user": _public_user(updated)}


@router.patch("/users/{user_id}/role", summary="Update user role (admin)")
async def update_user_role(
    user_id: str,
    payload: RoleUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Update a user's role."""
    updated = await user_repo.update_role(db, user_id, payload.role)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"user": _public_user(updated)}


@router.patch("/users/{user_id}/status", summary="Update user status (admin)")
async def update_user_status(
    user_id: str,
    payload: StatusUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Approve, reject, or set pending status for a user."""
    updated = await user_repo.update_status(db, user_id, payload.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"user": _public_user(updated)}


@router.get("/locations", summary="List all locations (admin)")
async def list_locations(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return all locations (greenhouses and flower shops)."""
    locations = await location_repo.get_all_locations(db)
    return {"locations": locations}


@router.patch("/locations/{location_id}", summary="Update location (admin)")
async def update_location(
    location_id: str,
    payload: LocationUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Update location name, type, or address."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        loc = await location_repo.get_location_by_id(db, location_id)
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found",
            )
        return {"location": loc}
    updated = await location_repo.update_location(
        db,
        location_id,
        name=updates.get("name"),
        location_type=updates.get("type"),
        address=updates.get("address"),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return {"location": updated}


@router.get("/devices", summary="List all devices (admin)")
async def list_devices(
    location_id: str | None = Query(None, description="Filter by location"),
    user_id: str | None = Query(None, description="Filter by user"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return all devices with location_name and user_name. Optional filters."""
    devices = await device_repo.get_all_devices(
        db, location_id=location_id, user_id=user_id
    )
    # Enrich with location and user names
    enriched = []
    for d in devices:
        loc = await location_repo.get_location_by_id(db, d.get("location_id", ""))
        user = await user_repo.get_user_by_id(db, d.get("user_id", ""))
        enriched.append({
            **d,
            "location_name": loc.get("name", "") if loc else "",
            "user_name": user.get("full_name", user.get("name", "")) if user else "",
        })
    return {"devices": enriched}


@router.post("/devices", summary="Create device (admin)")
async def create_device(
    payload: DeviceCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Register a new device."""
    existing = await device_repo.get_device_by_serial(
        db, payload.device_serial_number
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device serial number already registered",
        )
    device = await device_repo.create_device(
        db,
        location_id=payload.location_id,
        user_id=payload.user_id,
        name=payload.name,
        device_type=payload.type,
        device_serial_number=payload.device_serial_number,
    )
    return {"device": device}


@router.get("/devices/{device_id}", summary="Get device (admin)")
async def get_device(
    device_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return a single device by ID."""
    device = await device_repo.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return {"device": device}


@router.patch("/devices/{device_id}", summary="Update device (admin)")
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Update device name, type, or serial number."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        device = await device_repo.get_device_by_id(db, device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )
        return {"device": device}
    if "device_serial_number" in updates:
        existing = await device_repo.get_device_by_serial(
            db, updates["device_serial_number"]
        )
        if existing and existing["_id"] != device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device serial number already registered",
            )
    updated = await device_repo.update_device(
        db,
        device_id,
        name=updates.get("name"),
        device_type=updates.get("type"),
        device_serial_number=updates.get("device_serial_number"),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return {"device": updated}


@router.get("/devices/{device_id}/sensor-data", summary="Get device sensor data (admin)")
async def get_device_sensor_data(
    device_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Get sensor data for a device. FM devices: data from fm_sensor_data.
    Uses device_serial_number to query (ESP32 sends this as device_id)."""
    device = await device_repo.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    serial = device.get("device_serial_number") or device_id
    device_type = device.get("type", "").upper()

    # FM: query fm_sensor_data by device_id (ESP32 sends device_serial_number)
    if device_type == "FM":
        from app.db.mongodb import get_database

        fm_db = get_database()
        fm_coll = fm_db["fm_sensor_data"]
        cursor = fm_coll.find({"device_id": serial}).sort(
            [("timestamp", -1), ("_id", -1)]
        ).limit(limit)
        docs = await cursor.to_list(length=limit)
        readings = []
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            readings.append(doc)
        return {
            "device": device,
            "type": "FM",
            "device_id_for_sensor": serial,
            "count": len(readings),
            "readings": readings,
        }

    # INM, EOSM, EDAS: similar pattern - add as needed
    return {
        "device": device,
        "type": device_type,
        "device_id_for_sensor": serial,
        "count": 0,
        "readings": [],
        "message": f"Sensor data for {device_type} - add collection query as needed",
    }

