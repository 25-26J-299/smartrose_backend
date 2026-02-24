"""Admin-only endpoints for user and greenhouse management."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import greenhouses as gh_repo
from app.db.collections import users as user_repo
from app.db.mongodb import get_db
from app.models.user_models import RoleUpdate, StatusUpdate, UserPublic
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


@router.get("/users", summary="List all users (admin)")
async def list_users(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return all users. Excludes password_hash."""
    users = await user_repo.get_all_users(db)
    return {"users": [_public_user(u) for u in users]}


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


@router.get("/greenhouses", summary="List all greenhouses (admin)")
async def list_greenhouses(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict = Depends(_get_current_admin),
) -> dict:
    """Return all greenhouses and flower shops."""
    greenhouses = await gh_repo.get_all_greenhouses(db)
    return {"greenhouses": greenhouses}
