from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BaseResponse(BaseModel):
    """
    Base response model
    """
    status: str
    message: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BaseRequest(BaseModel):
    """
    Base request model
    """
    pass


