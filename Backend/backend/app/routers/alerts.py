from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.security import validar_api_key_dashboard, validar_api_key_edge
from app.database import influx_db
from app.models.alert import AlertData


router = APIRouter()


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
async def receive_alert_data(
    data: AlertData,
    api_key: str = Depends(validar_api_key_edge),
):
    try:
        influx_db.save_alert_data(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao gravar alerta no InfluxDB.") from exc

    return {
        "status": "sucesso",
        "mensagem": "Alerta registado no InfluxDB.",
        "camera": data.camera_id,
        "evento": data.evento,
        "media": data.media_filename,
    }


@router.get("/alerts")
async def fetch_alerts(
    minutos: int = Query(default=settings.DEFAULT_QUERY_MINUTES, ge=1, le=settings.MAX_QUERY_MINUTES),
    camera_id: str | None = Query(default=None, min_length=1, max_length=80),
    evento: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        dados = influx_db.get_recent_alerts(
            minutos=minutos,
            camera_id=camera_id,
            evento=evento,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao ler alertas do InfluxDB.") from exc

    return {
        "status": "sucesso",
        "total_registos": len(dados),
        "dados": dados,
    }


@router.get("/alerts/stats")
async def fetch_alert_stats(
    minutos: int = Query(default=settings.DEFAULT_QUERY_MINUTES, ge=1, le=settings.MAX_QUERY_MINUTES),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        stats = influx_db.get_alert_stats(minutos=minutos)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao calcular estatisticas.") from exc

    return {
        "status": "sucesso",
        "dados": stats,
    }


@router.get("/alerts/{camera_id}")
async def fetch_alerts_by_camera(
    camera_id: str,
    minutos: int = Query(default=settings.DEFAULT_QUERY_MINUTES, ge=1, le=settings.MAX_QUERY_MINUTES),
    limit: int = Query(default=100, ge=1, le=500),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        dados = influx_db.get_alerts_by_camera(camera_id=camera_id, minutos=minutos, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao ler alertas da camara.") from exc

    return {
        "status": "sucesso",
        "camera_id": camera_id,
        "total_registos": len(dados),
        "dados": dados,
    }
