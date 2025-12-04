from fastapi import APIRouter, HTTPException
from app.services.com2_service import Com2Service

router = APIRouter()
service = Com2Service()


@router.get("/com2")
async def get_com2():
    """
    Get com2 data
    """
    try:
        result = await service.get_data()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/com2")
async def create_com2(data: dict):
    """
    Create com2 data
    """
    try:
        result = await service.create_data(data)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


