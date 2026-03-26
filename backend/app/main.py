from fastapi import FastAPI
from app.routers import telemetry, alerts, media
from dotenv import load_dotenv
import os

# Carrega o .env que está dois níveis acima da pasta app
load_dotenv("../../.env")

app = FastAPI(title="IoT Surveillance System API")

# Inclui os routers que criámos antes
app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")

