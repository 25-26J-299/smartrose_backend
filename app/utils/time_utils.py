"""Time utility helpers."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)

