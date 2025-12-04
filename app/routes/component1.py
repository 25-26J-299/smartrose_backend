from fastapi import APIRouter, HTTPException
from app.services.com1_service import Com1Service

router = APIRouter()
service = Com1Service()


@router.get("/com1")
async def get_com1():
    """
    Get com1 data
    """
    try:
        result = await service.get_data()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/com1")
async def create_com1(data: dict):
    """
    Create com1 data
    """
    try:
        result = await service.create_data(data)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


