"""Authentication endpoints for user registration, login, and profile."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import locations as location_repo
from app.db.collections import users as user_repo
from app.db.mongodb import get_db
from app.models.user_models import (
    RoleUpdateLegacy,
    UserCreate,
    UserLogin,
    UserPublic,
)
from app.services.auth_service import (
    create_jwt,
    decode_jwt,
    hash_password,
    verify_password,
)

router = APIRouter()
bearer_scheme = HTTPBearer()
ALLOWED_ROLES = {"farmer", "florist"}


def _public_user(document: dict) -> dict:
    """Convert a stored user document to a public schema."""
    # Handle both new (full_name, role) and legacy (name, roles) schemas
    doc = dict(document)
    doc.setdefault("full_name", doc.get("name", ""))
    doc.setdefault("role", (doc.get("roles") or ["farmer"])[0])
    doc.setdefault("status", "pending")
    doc.setdefault("is_active", True)
    return UserPublic(**doc).model_dump(by_alias=True)


async def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Validate JWT and return the associated user document."""
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
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    return user


@router.post("/register", summary="Register a new user with location")
async def register_user(
    payload: UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Create user and location. User gets status=pending. Admin must approve user before login."""
    existing = await user_repo.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user_dict = payload.model_dump(exclude={"location"})
    user_dict["email"] = user_dict["email"].lower()
    user_dict["password_hash"] = hash_password(user_dict.pop("password"))
    user_dict["status"] = "pending"
    user_dict["is_active"] = True
    created_user = await user_repo.create_user(db, user_dict)

    loc = payload.location
    await location_repo.create_location(
        db,
        user_id=created_user["_id"],
        name=loc.name,
        location_type=loc.type,
        address=loc.address,
    )

    return {
        "message": "Registration successful. Your account and location are pending approval.",
        "user": _public_user(created_user),
    }


@router.post("/login", summary="Authenticate a user")
async def login_user(
    payload: UserLogin, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Validate credentials and return a JWT. Only approved and active users can log in."""
    user = await user_repo.verify_user_credentials(db, payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Admin can always log in regardless of status
    role = user.get("role") or (user.get("roles") or ["farmer"])[0]
    if role != "admin":
        if user.get("status") != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending approval. Please contact an administrator.",
            )
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated.",
            )

    await user_repo.update_last_login(db, user["_id"])

    token = create_jwt(
        user["_id"],
        user["email"],
        role=role,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _public_user(user),
    }


@router.get("/me", summary="Get current user profile")
async def get_me(current_user: dict = Depends(_get_current_user)) -> dict:
    """Return the authenticated user's profile."""
    return {"user": _public_user(current_user)}


@router.patch("/update-roles", summary="Update roles for the authenticated user")
async def update_roles(
    payload: RoleUpdateLegacy,
    current_user: dict = Depends(_get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Update the roles for the logged-in user (legacy endpoint)."""
    normalized_roles = [r.lower() for r in payload.roles]
    invalid = [r for r in normalized_roles if r not in ALLOWED_ROLES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid roles: {', '.join(invalid)}",
        )

    updated_user = await user_repo.update_roles(
        db, current_user["_id"], normalized_roles
    )
    role = updated_user.get("role") or normalized_roles[0]
    token = create_jwt(updated_user["_id"], updated_user["email"], role=role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _public_user(updated_user),
    }
