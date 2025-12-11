"""Authentication endpoints for user registration, login, and profile."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import users as user_repo
from app.db.mongodb import get_db
from app.models.user_models import RoleUpdate, UserCreate, UserLogin, UserPublic
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
    return UserPublic(**document).model_dump(by_alias=True)


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


@router.post("/register", summary="Register a new user")
async def register_user(
    payload: UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Create a new user account with hashed password."""
    existing = await user_repo.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user_dict = payload.model_dump()
    user_dict["email"] = user_dict["email"].lower()
    user_dict["password_hash"] = hash_password(user_dict.pop("password"))
    user_dict["roles"] = []

    created = await user_repo.create_user(db, user_dict)
    token = create_jwt(created["_id"], created["email"], created["roles"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _public_user(created),
    }


@router.post("/login", summary="Authenticate a user")
async def login_user(
    payload: UserLogin, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Validate credentials and return a JWT."""
    user = await user_repo.verify_user_credentials(db, payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_jwt(user["_id"], user["email"], user.get("roles", []))
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
    payload: RoleUpdate,
    current_user: dict = Depends(_get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Update the roles for the logged-in user."""
    normalized_roles = [role.lower() for role in payload.roles]
    invalid = [role for role in normalized_roles if role not in ALLOWED_ROLES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid roles: {', '.join(invalid)}",
        )

    updated_user = await user_repo.update_roles(
        db, current_user["_id"], normalized_roles
    )
    token = create_jwt(
        updated_user["_id"], updated_user["email"], updated_user.get("roles", [])
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _public_user(updated_user),
    }

