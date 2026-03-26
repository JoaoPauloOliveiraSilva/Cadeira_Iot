from fastapi import APIRouter
router = APIRouter()

@router.get("/telemetry/test")
def test():
    return {"msg": "Telemetry router active"}

