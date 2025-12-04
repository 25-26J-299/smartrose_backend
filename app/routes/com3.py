from fastapi import APIRouter, HTTPException
from app.services.com3_service import Com3Service

router = APIRouter()
service = Com3Service()


@router.get("/com3")
async def get_com3():
    """
    Get com3 data
    """
    try:
        result = await service.get_data()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/com3")
async def create_com3(data: dict):
    """
    Create com3 data
    """
    try:
        result = await service.create_data(data)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


