from fastapi import APIRouter
from app.models.alert import AlertData       
from app.database import influx_db           
from fastapi import Depends
from app.core.security import validar_api_key
router = APIRouter()

@router.post("/alerts")
async def receive_alert_data(data: AlertData):
    
    influx_db.save_alert_data(data)
    
    return {
        "status": "sucesso", 
        "mensagem": "Alerta registado no InfluxDB",
        "camera": data.camera_id,
        "evento": data.evento,
        "media": data.media_filename
    }
    
@router.get("/alerts")
async def fetch_alerts(minutos: int):

    dados = influx_db.get_recent_alerts(minutos=minutos)
    
    return {
        "status": "sucesso",
        "total_registos": len(dados),
        "dados": dados
    }
    
@router.get("/alerts/stats")
async def fetch_alert_stats(minutos: int):
    """
    Devolve um resumo estatístico (ex: número total de alertas).
    """
    stats = influx_db.get_alert_stats(minutos=minutos)
    
    return {
        "status": "sucesso",
        "dados": stats
    }

@router.get("/alerts/{camera_id}")
async def fetch_alerts_by_camera(camera_id: str, minutos: int):
    """
    Filtra o histórico de alertas para uma câmara específica.
    """
    dados = influx_db.get_alerts_by_camera(camera_id=camera_id, minutos=minutos)
    
    return {
        "status": "sucesso",
        "camera_id": camera_id,
        "total_registos": len(dados),
        "dados": dados
    }