"""Timezone utility functions for converting UTC to Sri Lankan time (IST)."""

from datetime import datetime, timezone, timedelta


# Sri Lankan timezone offset: UTC+5:30
IST_OFFSET = timedelta(hours=5, minutes=30)


def utc_to_ist(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to Sri Lankan time (IST - UTC+5:30).
    
    Args:
        utc_dt: UTC datetime (should be timezone-aware with UTC timezone)
        
    Returns:
        IST datetime as a timezone-naive datetime with IST time values
    """
    # Ensure the input is UTC
    if utc_dt.tzinfo is None:
        # If timezone-naive, assume it's UTC
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    elif utc_dt.tzinfo != timezone.utc:
        # Convert to UTC if it's in a different timezone
        utc_dt = utc_dt.astimezone(timezone.utc)
    
    # Add IST offset (UTC+5:30)
    ist_dt = utc_dt + IST_OFFSET
    
    # Return as timezone-naive datetime with IST values
    # This is what the frontend expects
    return ist_dt.replace(tzinfo=None)


def convert_datetime_fields(doc: dict, fields: list[str]) -> dict:
    """Convert specified datetime fields in a document from UTC to IST.
    
    Args:
        doc: Document dictionary from MongoDB
        fields: List of field names to convert
        
    Returns:
        Document with converted datetime fields
    """
    result = doc.copy()
    for field in fields:
        if field in result and result[field] is not None:
            value = result[field]
            # Handle datetime objects from MongoDB
            if isinstance(value, datetime):
                result[field] = utc_to_ist(value)
            # Handle ISO string format
            elif isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    result[field] = utc_to_ist(dt).isoformat()
                except (ValueError, AttributeError):
                    pass  # Keep original value if parsing fails
    return result

