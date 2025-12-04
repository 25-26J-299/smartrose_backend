from fastapi import APIRouter, HTTPException
from app.services.com4_service import Com4Service

router = APIRouter()
service = Com4Service()


@router.get("/com4")
async def get_com4():
    """
    Get com4 data
    """
    try:
        result = await service.get_data()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/com4")
async def create_com4(data: dict):
    """
    Create com4 data
    """
    try:
        result = await service.create_data(data)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


