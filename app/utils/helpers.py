from typing import Any, Dict
from datetime import datetime


def format_response(data: Any, message: str = "Success") -> Dict[str, Any]:
    """
    Format API response
    """
    return {
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }


def format_error(message: str, error_code: str = "UNKNOWN_ERROR") -> Dict[str, Any]:
    """
    Format error response
    """
    return {
        "status": "error",
        "message": message,
        "error_code": error_code,
        "timestamp": datetime.utcnow().isoformat()
    }


