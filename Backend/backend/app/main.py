import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.core.config import settings
from app.database import influx_db
from app.models.alert import AlertData
from app.routers import alerts, dashboard, media


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IoT Surveillance System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(media.router, prefix="/api/v1", tags=["media"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if settings.MQTT_ENABLED:
    from fastapi_mqtt import FastMQTT, MQTTConfig

    mqtt_config = MQTTConfig(
        host=settings.MQTT_BROKER,
        port=settings.MQTT_PORT,
        username=settings.MQTT_USERNAME,
        password=settings.MQTT_PASSWORD,
    )

    mqtt = FastMQTT(config=mqtt_config)
    mqtt.init_app(app)

    @mqtt.subscribe("surveillance/cameras/alerts")
    async def message_to_topic(client, topic, payload, qos, properties):
        try:
            dados_json = json.loads(payload.decode())
            alerta = AlertData(**dados_json)
            influx_db.save_alert_data(alerta)
            logger.info("Alerta via MQTT recebido: evento=%s camera=%s", alerta.evento, alerta.camera_id)
        except (json.JSONDecodeError, ValidationError):
            logger.warning("Mensagem MQTT invalida recebida no topico %s", topic)
        except Exception:
            logger.exception("Erro ao processar mensagem MQTT no topico %s", topic)
else:
    logger.info("MQTT desativado. A API vai aceitar alertas via HTTP.")
