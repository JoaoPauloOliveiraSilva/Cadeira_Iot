"""
IoT Surveillance API — cliente de teste em Python
Cobre: POST /media/full, MQTT

USO:
    python edge_simulator.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─── Configuração ────────────────────────────────────────────────────────────

BASE_URL  = "http://100.118.101.103:32080"
API_KEY   = "SeiLa"   # API_KEY_EDGE

MQTT_HOST  = "100.118.101.103"
MQTT_PORT  = 31883
MQTT_TOPIC = "surveillance/cameras/alerts"

# ─── Ficheiro de media a enviar ───────────────────────────────────────────────

VIDEO_FILE = Path("~/Desktop/IOT/teste/teste_video.mp4").expanduser()

# ─── Dados do alerta ──────────────────────────────────────────────────────────

CAMERA_ID   = "cam-frente-01"
EVENTO      = "intruso_detectado"
LOCALIZACAO = "entrada-norte"
CONFIANCA   = "0.94"

# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "X-API-Key": API_KEY,
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _print_response(r: requests.Response) -> None:
    print(f"  Status : {r.status_code}")
    try:
        print(f"  Body   : {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
    except Exception:
        print(f"  Body   : {r.text}")
    print()


def _guess_content_type(path: Path) -> str:
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".wav": "audio/wav", ".mp3": "audio/mpeg",
    }.get(path.suffix.lower(), "application/octet-stream")


def _resolve_file(filepath: str | Path) -> Path | None:
    """Resolve o caminho do ficheiro e valida que existe."""
    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        print(f"  ERRO: Ficheiro não encontrado: {p}\n")
        return None
    if not p.is_file():
        print(f"  ERRO: O caminho não é um ficheiro: {p}\n")
        return None
    ct = _guess_content_type(p)
    if ct == "application/octet-stream":
        print(f"  AVISO: Extensão '{p.suffix}' não reconhecida — será enviada como application/octet-stream.")
        print("  O servidor pode rejeitar com 415. Usa .mp4, .jpg, .png, .webm, .wav ou .mp3.\n")
    return p


# ─── 1. Health check ─────────────────────────────────────────────────────────

def test_health() -> bool:
    print("── Health check ──────────────────────────────")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        _print_response(r)
        return r.ok
    except requests.exceptions.ConnectionError:
        print(f"  ERRO: Não foi possível ligar a {BASE_URL}\n")
        return False


# ─── 2. Enviar alerta em JSON (sem ficheiro) ──────────────────────────────────

def test_post_alert_json() -> requests.Response | None:
    print("── POST /api/v1/alerts (JSON, sem media) ─────")
    payload = {
        "camera_id"  : "cam-01",
        "evento"     : "intruso_detectado",
        "confianca"  : 0.93,
        "localizacao": "entrada-norte",
        "media_tipo" : "image",
        "timestamp"  : datetime.now(timezone.utc).isoformat(),
    }
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/alerts",
            headers={**HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        _print_response(r)
        return r
    except requests.exceptions.RequestException as exc:
        print(f"  ERRO: {exc}\n")
        return None


# ─── 3. Upload de ficheiro (só media, sem alerta) ─────────────────────────────

def test_upload_media(filepath: str | Path) -> str | None:
    print("── POST /api/v1/media/upload ─────────────────")
    p = _resolve_file(filepath)
    if p is None:
        return None

    content_type = _guess_content_type(p)
    print(f"  Ficheiro    : {p.name} ({p.stat().st_size:,} bytes)")
    print(f"  Content-Type: {content_type}")

    try:
        with p.open("rb") as f:
            r = requests.post(
                f"{BASE_URL}/api/v1/media/upload",
                headers=HEADERS,
                files={"file": (p.name, f, content_type)},
                data={"camera_id": "cam-01"},
                timeout=120,
            )
        _print_response(r)
        if r.ok:
            return r.json().get("nome_ficheiro")
        return None
    except requests.exceptions.RequestException as exc:
        print(f"  ERRO: {exc}\n")
        return None


# ─── 4. Alerta completo (ficheiro + metadados numa só chamada) ────────────────

def test_media_full(filepath: str | Path) -> requests.Response | None:
    print("── POST /api/v1/media/full ───────────────────")
    p = _resolve_file(filepath)
    if p is None:
        return None

    content_type = _guess_content_type(p)
    print(f"  Ficheiro    : {p.name} ({p.stat().st_size:,} bytes)")
    print(f"  Content-Type: {content_type}")

    # Deriva media_tipo a partir do content_type real do ficheiro
    if content_type.startswith("video/"):
        media_tipo = "video"
    elif content_type.startswith("image/"):
        media_tipo = "image"
    elif content_type.startswith("audio/"):
        media_tipo = "audio"
    else:
        media_tipo = "video"  # fallback

    try:
        with p.open("rb") as f:
            r = requests.post(
                f"{BASE_URL}/api/v1/media/full",
                headers=HEADERS,
                files={"file": (p.name, f, content_type)},
                data={
                    "camera_id"  : CAMERA_ID,
                    "evento"     : EVENTO,
                    "localizacao": LOCALIZACAO,
                    "confianca"  : CONFIANCA,
                    "media_tipo" : media_tipo,
                },
                timeout=120,
            )
        _print_response(r)
        return r
    except requests.exceptions.RequestException as exc:
        print(f"  ERRO: {exc}\n")
        return None


# ─── 5. MQTT ─────────────────────────────────────────────────────────────────

def test_mqtt() -> None:
    """
    Envia apenas metadados via MQTT — sem media associada.
    O alerta aparecerá no frontend sem ficheiro de preview.
    Para alertas com video/imagem usa test_media_full().
    """
    print("── MQTT publish (sem media) ──────────────────")
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("  paho-mqtt não instalado. Corre: pip install paho-mqtt\n")
        return

    payload = {
        "camera_id"  : "cam-03",
        "evento"     : "movimento_suspeito",
        "confianca"  : 0.75,
        "localizacao": "parque-sul",
        "media_tipo" : "video",
        "timestamp"  : datetime.now(timezone.utc).isoformat(),
    }

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    except OSError as exc:
        print(f"  ERRO: Ligação recusada em {MQTT_HOST}:{MQTT_PORT} — {exc}")
        print("  Verifica se o pod mosquitto está a correr:")
        print("    kubectl get pods -n iot-surveillance")
        print(f"    nc -zv {MQTT_HOST} {MQTT_PORT}")
        print()
        return

    client.loop_start()
    result = client.publish(MQTT_TOPIC, json.dumps(payload), qos=0)
    result.wait_for_publish(timeout=5.0)
    client.loop_stop()
    client.disconnect()

    print(f"  Tópico : {MQTT_TOPIC}")
    print(f"  Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print(f"  rc     : {result.rc}  (0 = sucesso)")
    print(f"  NOTA   : Este alerta não tem media — aparecerá 'Sem preview' no frontend.")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_health()
    r = test_media_full(VIDEO_FILE)
    if r is not None:
        print(f"Resultado final: {r.status_code} {'OK' if r.ok else 'ERRO'}")