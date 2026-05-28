import os
import time
import requests
import shutil
import json
from pathlib import Path
from datetime import datetime, timezone

# ─── Configuration (from your friend's updated code) ─────────────────────────
BASE_URL   = "http://100.118.101.103:32080"
API_KEY    = "SeiLa"

MQTT_HOST  = "100.118.101.103"
MQTT_PORT  = 31883
MQTT_TOPIC = "surveillance/cameras/alerts"

# ─── Your local folders ──────────────────────────────────────────────────────
WATCH_FOLDERS = [
    os.path.expanduser("~/Desktop/kept_clips"),      # video
    os.path.expanduser("~/Desktop/send_backend")     # audio
]
ALLOWED_EXTENSIONS = {".mp4", ".wav", ".jpg", ".png"}
ARCHIVE_FOLDER = os.path.expanduser("~/Desktop/uploaded_media")
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

# ─── Default alert metadata ──────────────────────────────────────────────────
CAMERA_ID   = "cam-frente-01"
EVENTO      = "intruso_detectado"
LOCALIZACAO = "entrada-norte"
CONFIANCA   = "0.94"

# ─── Globals ─────────────────────────────────────────────────────────────────
HEADERS = {"X-API-Key": API_KEY}
CHECK_INTERVAL = 5
processed_files = set()

# ─── Helpers (adapted from your friend's code) ───────────────────────────────
def _guess_content_type(path: Path) -> str:
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".wav": "audio/wav", ".mp3": "audio/mpeg",
    }.get(path.suffix.lower(), "application/octet-stream")

def _media_tipo_from_content_type(content_type: str) -> str:
    if content_type.startswith("video/"):
        return "video"
    elif content_type.startswith("image/"):
        return "image"
    elif content_type.startswith("audio/"):
        return "audio"
    return "video"  # fallback

def upload_media_full(file_path: Path) -> bool:
    """POST /api/v1/media/full – envia ficheiro + metadados."""
    content_type = _guess_content_type(file_path)
    media_tipo = _media_tipo_from_content_type(content_type)

    print(f"  📁 Ficheiro: {file_path.name} ({file_path.stat().st_size:,} bytes)")
    print(f"  📋 Content-Type: {content_type}")

    try:
        with file_path.open("rb") as f:
            r = requests.post(
                f"{BASE_URL}/api/v1/media/full",
                headers=HEADERS,
                files={"file": (file_path.name, f, content_type)},
                data={
                    "camera_id": CAMERA_ID,
                    "evento": EVENTO,
                    "localizacao": LOCALIZACAO,
                    "confianca": CONFIANCA,
                    "media_tipo": media_tipo,
                },
                timeout=120,
            )
        if r.ok:
            print(f"  ✅ Upload OK: {r.json()}")
            return True
        else:
            print(f"  ❌ Upload failed (Status {r.status_code}): {r.text}")
            return False
    except Exception as e:
        print(f"  ❌ Upload error: {e}")
        return False

def publish_mqtt(metadata: dict) -> None:
    """Optional MQTT alert (metadata only, no media file)."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return

    payload = {
        "camera_id": metadata["camera_id"],
        "evento": metadata["evento"],
        "confianca": metadata["confianca"],
        "localizacao": metadata["localizacao"],
        "media_tipo": metadata["media_tipo"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            client = mqtt.Client()
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.publish(MQTT_TOPIC, json.dumps(payload))
        client.disconnect()
        print(f"  📡 MQTT alert sent")
    except Exception as e:
        print(f"  ⚠️ MQTT error: {e}")

# ─── Main loop ───────────────────────────────────────────────────────────────
print("📁 Media uploader for friend's API (/media/full)")
print(f"   Base URL: {BASE_URL}")
print(f"   Watching: {WATCH_FOLDERS}")
print("   Press Ctrl+C to stop.")

try:
    while True:
        for watch_dir in WATCH_FOLDERS:
            if not os.path.exists(watch_dir):
                continue
            for file_path in Path(watch_dir).glob("*"):
                if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                if file_path in processed_files:
                    continue
                if file_path.stat().st_size == 0:
                    continue
                if time.time() - file_path.stat().st_mtime < 2:
                    continue

                processed_files.add(file_path)
                print(f"\n🆕 New file: {file_path.name}")
                if upload_media_full(file_path):
                    # Move to archive
                    dest = os.path.join(ARCHIVE_FOLDER, file_path.name)
                    shutil.move(str(file_path), dest)
                    print(f"  ➡️ Moved to {dest}")

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print("\n🛑 Stopped.")