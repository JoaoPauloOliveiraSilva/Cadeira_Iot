from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from app.core.config import settings
from app.models.alert import AlertData 
from influxdb_client.client.query_api import QueryApi

client = InfluxDBClient(url="http://localhost:32086", token=settings.INFLUX_TOKEN, org=settings.INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()  

def save_alert_data(data: AlertData):  
    """
    Recebe um objeto AlertData (do YOLO/Câmara), formata-o como um Point e grava no InfluxDB.
    """
    
    ponto = (Point("Alert")
             .tag("camera_id", data.camera_id)
             .tag("evento", data.evento)
             .tag("localizacao", data.localizacao)
             .tag("media_tipo", data.media_tipo)
             .field("confianca", data.confianca)
             .field("media_filename", data.media_filename))
    
    if data.timestamp:
        ponto = ponto.time(data.timestamp, WritePrecision.NS)

    try:
        write_api.write(bucket=settings.INFLUX_BUCKET, org=settings.INFLUX_ORG, record=ponto)
        print(f"✅ Alerta da câmara {data.camera_id} gravado no InfluxDB!")
    except Exception as e:
        print(f"❌ Erro ao gravar no InfluxDB: {e}")


def get_recent_alerts(minutos: int):
    
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
    """
    
    try:
        tabelas = query_api.query(query=query,org=settings.INFLUX_ORG)
        resultados = []
        for tabela in tabelas:
            for registo in tabela.records:
                resultados.append({
                    "timestamp": registo.get_time().isoformat(),
                    "camera_id": registo.values.get("camera_id"),
                    "evento": registo.values.get("evento"),
                    "localizacao": registo.values.get("localizacao"),
                    "confianca": registo.values.get("confianca"),
                    "media_filename": registo.values.get("media_filename")
                })
                
        return resultados
    except Exception as e:
        print(f" Erro ao ler do InfluxDB: {e}")
        return []
    
    
def get_alerts_by_camera(camera_id: str, minutos: int):
    flux_query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> filter(fn: (r) => r["camera_id"] == "{camera_id}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
    """
    try:
        tabelas = query_api.query(query=flux_query, org=settings.INFLUX_ORG)
        resultados = []
        for tabela in tabelas:
            for registo in tabela.records:
                resultados.append({
                    "timestamp": registo.get_time().isoformat(),
                    "evento": registo.values.get("evento"),
                    "localizacao": registo.values.get("localizacao"),
                    "confianca": registo.values.get("confianca"),
                    "media_filename": registo.values.get("media_filename")
                })
        return resultados
    except Exception as e:
        print(f" Erro ao ler câmara do InfluxDB: {e}")
        return []

def get_alert_stats(minutos: int):
    """Devolve o número total de alertas nas últimas 24h (1440 minutos)."""
    flux_query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> filter(fn: (r) => r["_field"] == "confianca")
          |> count()
    """
    try:
        tabelas = query_api.query(query=flux_query, org=settings.INFLUX_ORG)
        total = 0
        for tabela in tabelas:
            for registo in tabela.records:
                total += registo.get_value() 
                
        return {"minutos_analisados": minutos, "total_alertas": total}
    except Exception as e:
        print(f" Erro nas estatísticas: {e}")
        return {"minutos_analisados": minutos, "total_alertas": 0}