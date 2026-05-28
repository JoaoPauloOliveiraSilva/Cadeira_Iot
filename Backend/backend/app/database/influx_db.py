import json
from collections import defaultdict
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from app.core.config import settings
from app.models.alert import AlertData


client = InfluxDBClient(
    url=settings.INFLUXDB_URL,
    token=settings.INFLUX_TOKEN,
    org=settings.INFLUX_ORG,
)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()


def _flux_string(value: str) -> str:
    return json.dumps(value)


def _safe_minutes(minutos: int | None) -> int:
    if minutos is None:
        return settings.DEFAULT_QUERY_MINUTES
    return max(1, min(int(minutos), settings.MAX_QUERY_MINUTES))


def save_alert_data(data: AlertData) -> None:
    timestamp = data.timestamp or datetime.now(timezone.utc)
    ponto = (
        Point("Alert")
        .tag("camera_id", data.camera_id)
        .tag("evento", data.evento)
        .tag("localizacao", data.localizacao)
        .tag("media_tipo", data.media_tipo)
        .field("confianca", data.confianca)
        .field("media_filename", data.media_filename or "")
        .time(timestamp, WritePrecision.NS)
    )

    write_api.write(bucket=settings.INFLUX_BUCKET, org=settings.INFLUX_ORG, record=ponto)


def _records_to_alerts(tabelas) -> list[dict]:
    resultados = []
    for tabela in tabelas:
        for registo in tabela.records:
            media_filename = registo.values.get("media_filename") or None
            resultados.append(
                {
                    "timestamp": registo.get_time().isoformat(),
                    "camera_id": registo.values.get("camera_id"),
                    "evento": registo.values.get("evento"),
                    "localizacao": registo.values.get("localizacao"),
                    "media_tipo": registo.values.get("media_tipo"),
                    "confianca": registo.values.get("confianca"),
                    "media_filename": media_filename,
                }
            )
    return resultados


def get_recent_alerts(
    minutos: int | None = None,
    camera_id: str | None = None,
    evento: str | None = None,
    limit: int = 100,
) -> list[dict]:
    minutos = _safe_minutes(minutos)
    limit = max(1, min(int(limit), 500))

    filters = ['r["_measurement"] == "Alert"']
    if camera_id:
        filters.append(f'r["camera_id"] == {_flux_string(camera_id)}')
    if evento:
        filters.append(f'r["evento"] == {_flux_string(evento)}')

    filter_query = " and ".join(filters)
    query = f"""
        from(bucket: {_flux_string(settings.INFLUX_BUCKET)})
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => {filter_query})
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
    """
    tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
    return _records_to_alerts(tabelas)


def get_alerts_by_camera(camera_id: str, minutos: int | None = None, limit: int = 100) -> list[dict]:
    return get_recent_alerts(minutos=minutos, camera_id=camera_id, limit=limit)


def get_alert_stats(minutos: int | None = None) -> dict:
    minutos = _safe_minutes(minutos)
    flux_query = f"""
        from(bucket: {_flux_string(settings.INFLUX_BUCKET)})
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> filter(fn: (r) => r["_field"] == "confianca")
          |> count()
    """
    tabelas = query_api.query(query=flux_query, org=settings.INFLUX_ORG)
    total = 0
    for tabela in tabelas:
        for registo in tabela.records:
            total += registo.get_value()

    return {"minutos_analisados": minutos, "total_alertas": total}


def get_dashboard_summary(minutos: int | None = None) -> dict:
    dados = get_recent_alerts(minutos=minutos, limit=500)
    cameras = {item["camera_id"] for item in dados if item.get("camera_id")}
    confidences = [item["confianca"] for item in dados if isinstance(item.get("confianca"), (int, float))]
    eventos = defaultdict(int)
    for item in dados:
        if item.get("evento"):
            eventos[item["evento"]] += 1

    return {
        "minutos_analisados": _safe_minutes(minutos),
        "total_alertas": len(dados),
        "cameras_ativas": len(cameras),
        "confianca_media": round(sum(confidences) / len(confidences), 4) if confidences else 0,
        "eventos": dict(eventos),
    }


def get_alert_timeline(minutos: int | None = None, every: str = "1h") -> list[dict]:
    minutos = _safe_minutes(minutos)
    flux_query = f"""
        from(bucket: {_flux_string(settings.INFLUX_BUCKET)})
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> filter(fn: (r) => r["_field"] == "confianca")
          |> aggregateWindow(every: {every}, fn: count, createEmpty: false)
          |> yield(name: "count")
    """
    tabelas = query_api.query(query=flux_query, org=settings.INFLUX_ORG)
    resultados = []
    for tabela in tabelas:
        for registo in tabela.records:
            resultados.append(
                {
                    "timestamp": registo.get_time().isoformat(),
                    "total_alertas": registo.get_value(),
                }
            )
    return resultados


def get_alerts_by_camera_stats(minutos: int | None = None) -> list[dict]:
    minutos = _safe_minutes(minutos)
    flux_query = f"""
        from(bucket: {_flux_string(settings.INFLUX_BUCKET)})
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> filter(fn: (r) => r["_field"] == "confianca")
          |> group(columns: ["camera_id"])
          |> count()
    """
    tabelas = query_api.query(query=flux_query, org=settings.INFLUX_ORG)
    resultados = []
    for tabela in tabelas:
        for registo in tabela.records:
            resultados.append(
                {
                    "camera_id": registo.values.get("camera_id"),
                    "total_alertas": registo.get_value(),
                }
            )
    return resultados
