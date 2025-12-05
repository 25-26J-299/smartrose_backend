"""Helpers for building consistent API responses."""

from typing import Any, Dict, Optional


def success_response(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Standard success envelope."""
    return {"status": "success", "message": message, "data": data or {}}

