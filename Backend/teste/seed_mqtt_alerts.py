import argparse
import json
import random
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt


CAMERAS = [
    ("cam_frente_01", "Portao Principal"),
    ("cam_garagem_01", "Garagem"),
    ("cam_jardim_01", "Jardim"),
    ("cam_corredor_01", "Corredor"),
    ("cam_armazem_01", "Armazem"),
]

EVENTOS = [
    "pessoa_detectada",
    "intruso_detectado",
    "som_suspeito",
    "movimento_suspeito",
]


def build_alert(index: int, hours_back: int) -> dict:
    camera_id, localizacao = random.choice(CAMERAS)
    evento = random.choices(EVENTOS, weights=[45, 20, 15, 20], k=1)[0]
    timestamp = datetime.now(timezone.utc) - timedelta(
        seconds=random.randint(0, max(hours_back * 3600, 1))
    )

    return {
        "camera_id": camera_id,
        "evento": evento,
        "confianca": round(random.uniform(0.55, 0.99), 3),
        "localizacao": localizacao,
        "media_tipo": "video",
        "media_filename": f"{camera_id}/seed/alerta_{index:04d}.mp4",
        "timestamp": timestamp.isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Publica alertas MQTT de teste para popular o InfluxDB.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=31883)
    parser.add_argument("--topic", default="surveillance/cameras/alerts")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--hours-back", type=int, default=24)
    parser.add_argument("--delay", type=float, default=0.02)
    args = parser.parse_args()

    client = mqtt.Client(client_id=f"seed_mqtt_alerts_{random.randint(1000, 9999)}")
    client.connect(args.host, args.port, 60)

    for index in range(1, args.count + 1):
        payload = build_alert(index, args.hours_back)
        client.publish(args.topic, json.dumps(payload), qos=0)
        print(f"[{index}/{args.count}] {payload['camera_id']} {payload['evento']} {payload['confianca']}")
        time.sleep(args.delay)

    client.disconnect()


if __name__ == "__main__":
    main()
