"""Time utility helpers."""

from datetime import datetime, timedelta, timezone

# Sri Lanka Standard Time (UTC+5:30) — no DST observed
SLST = timezone(timedelta(hours=5, minutes=30))


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def epoch_to_utc(epoch: int) -> datetime:
    """Convert a UTC epoch integer to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def epoch_to_slst(epoch: int) -> datetime:
    """Convert a UTC epoch integer to Sri Lanka Standard Time (UTC+5:30)."""
    return datetime.fromtimestamp(epoch, tz=SLST)

