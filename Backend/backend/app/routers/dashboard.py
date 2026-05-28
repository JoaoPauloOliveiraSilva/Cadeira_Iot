from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.core.security import validar_api_key_dashboard
from app.database import influx_db


router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(
    minutos: int = Query(default=settings.DEFAULT_QUERY_MINUTES, ge=1, le=settings.MAX_QUERY_MINUTES),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        dados = influx_db.get_dashboard_summary(minutos=minutos)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao calcular resumo da dashboard.") from exc

    return {"status": "sucesso", "dados": dados}


@router.get("/dashboard/timeline")
async def dashboard_timeline(
    minutos: int = Query(default=settings.DEFAULT_QUERY_MINUTES, ge=1, le=settings.MAX_QUERY_MINUTES),
    bucket: str = Query(default="1h", pattern=r"^\d+[mhd]$"),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        dados = influx_db.get_alert_timeline(minutos=minutos, every=bucket)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao calcular timeline.") from exc

    return {"status": "sucesso", "dados": dados}


@router.get("/dashboard/cameras")
async def dashboard_cameras(
    minutos: int = Query(default=settings.DEFAULT_QUERY_MINUTES, ge=1, le=settings.MAX_QUERY_MINUTES),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        dados = influx_db.get_alerts_by_camera_stats(minutos=minutos)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao calcular estatisticas por camara.") from exc

    return {"status": "sucesso", "dados": dados}
