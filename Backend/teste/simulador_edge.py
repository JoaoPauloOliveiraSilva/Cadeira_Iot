import os
from datetime import datetime, timezone
from pathlib import Path

import requests


API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1/media/full")
API_KEY_EDGE = os.getenv("API_KEY_EDGE", "trocar-esta-chave")
ARQUIVO_TESTE = Path(__file__).with_name("teste_video.mp4")


def simular_deteccao():
    if not ARQUIVO_TESTE.exists():
        raise FileNotFoundError(f"Ficheiro de teste nao encontrado: {ARQUIVO_TESTE}")

    dados_alerta = {
        "camera_id": "cam_frente_01",
        "evento": "pessoa_detectada",
        "confianca": "0.92",
        "localizacao": "Portao Principal",
        "media_tipo": "video",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    headers = {"X-API-Key": API_KEY_EDGE}
    with ARQUIVO_TESTE.open("rb") as file_handle:
        files = {"file": (ARQUIVO_TESTE.name, file_handle, "video/mp4")}
        response = requests.post(
            API_URL,
            data=dados_alerta,
            files=files,
            headers=headers,
            timeout=30,
        )

    print(f"Status: {response.status_code}")
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    simular_deteccao()
