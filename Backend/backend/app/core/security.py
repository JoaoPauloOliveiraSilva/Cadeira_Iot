import hmac

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.core.config import settings


API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def _compare_api_key(received_key: str | None, expected_key: str | None) -> bool:
    if not received_key or not expected_key:
        return False
    return hmac.compare_digest(received_key, expected_key)


async def validar_api_key_edge(api_key: str = Security(api_key_header)):
    if _compare_api_key(api_key, settings.API_KEY_EDGE):
        return api_key

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado: API key do dispositivo Edge invalida ou ausente.",
    )


async def validar_api_key_dashboard(api_key: str = Security(api_key_header)):
    expected_key = settings.API_KEY_DASHBOARD or settings.API_KEY_EDGE
    if _compare_api_key(api_key, expected_key):
        return api_key

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado: API key da dashboard invalida ou ausente.",
    )


validar_api_key = validar_api_key_edge
