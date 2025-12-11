"""Authentication utilities for hashing and JWT handling."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Configure passlib with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    # bcrypt only supports up to 72 bytes; truncate to avoid runtime errors
    safe_password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(safe_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt(
    subject: str, email: str, roles: Optional[list[str]] = None
) -> str:
    """Create a signed JWT for the given subject/email."""
    expire_minutes = getattr(settings, "jwt_expire_minutes", 60)
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "email": email,
        "roles": roles or [],
        "exp": expire,
    }
    return jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=getattr(settings, "jwt_algorithm", "HS256"),
    )


def decode_jwt(token: str) -> Optional[dict]:
    """Decode a JWT and return its payload or None if invalid/expired."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[getattr(settings, "jwt_algorithm", "HS256")],
        )
    except JWTError:
        return None

