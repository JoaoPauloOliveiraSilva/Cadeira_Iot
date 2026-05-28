from datetime import datetime
import hmac
import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.security import validar_api_key_dashboard, validar_api_key_edge
from app.database import influx_db, minio_db
from app.models.alert import AlertData


router = APIRouter()
logger = logging.getLogger(__name__)


async def _read_upload_file(file: UploadFile) -> bytes:
    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.allowed_media_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de ficheiro nao permitido: {content_type}",
        )

    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ficheiro demasiado grande.",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Ficheiro vazio.")
    return data


@router.post("/media/upload", status_code=status.HTTP_201_CREATED)
async def upload_media_file(
    file: UploadFile = File(...),
    camera_id: str | None = Form(default=None),
    api_key: str = Depends(validar_api_key_edge),
):
    file_data = await _read_upload_file(file)

    try:
        saved_filename = minio_db.upload_media(
            file_data=file_data,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            camera_id=camera_id,
        )
    except Exception as exc:
        logger.exception("Falha ao gravar ficheiro no MinIO.")
        raise HTTPException(status_code=502, detail="Falha ao gravar ficheiro no MinIO.") from exc

    return {
        "status": "sucesso",
        "mensagem": "Ficheiro guardado com sucesso no Object Storage.",
        "nome_ficheiro": saved_filename,
        "tamanho_bytes": len(file_data),
    }


@router.post("/media/full", status_code=status.HTTP_201_CREATED)
async def create_full_alert(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    evento: str = Form(...),
    localizacao: str = Form(...),
    confianca: float = Form(...),
    media_tipo: str = Form(...),
    timestamp: datetime | None = Form(default=None),
    api_key: str = Depends(validar_api_key_edge),
):
    file_data = await _read_upload_file(file)

    try:
        data = AlertData(
            camera_id=camera_id,
            evento=evento,
            localizacao=localizacao,
            confianca=confianca,
            media_tipo=media_tipo,
            timestamp=timestamp,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Dados de alerta invalidos.") from exc

    try:
        saved_filename = minio_db.upload_media(
            file_data=file_data,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            camera_id=data.camera_id,
        )
        data.media_filename = saved_filename
        influx_db.save_alert_data(data)
    except Exception as exc:
        if "saved_filename" in locals():
            minio_db.delete_media(saved_filename)
        logger.exception("Falha ao processar alerta completo.")
        raise HTTPException(status_code=502, detail="Falha ao processar alerta completo.") from exc

    return {
        "status": "sucesso",
        "mensagem": "Alerta completo processado e gravado.",
        "media_filename": saved_filename,
    }


@router.get("/media/url")
async def get_media_url(
    filename: str = Query(..., min_length=1, max_length=255),
    expires_minutes: int = Query(default=15, ge=1, le=60),
    api_key: str = Depends(validar_api_key_dashboard),
):
    try:
        url = minio_db.get_media_url(filename, expires_minutes=expires_minutes)
    except Exception as exc:
        logger.exception("Falha ao gerar URL de media: %s", filename)
        raise HTTPException(status_code=404, detail="Media nao encontrada ou URL indisponivel.") from exc

    return {
        "status": "sucesso",
        "filename": filename,
        "url": url,
        "expires_minutes": expires_minutes,
    }


def _iter_minio_response(response):
    try:
        for chunk in response.stream(1024 * 1024):
            yield chunk
    finally:
        response.close()
        response.release_conn()


@router.get("/media/stream")
async def stream_media(
    filename: str = Query(..., min_length=1, max_length=255),
    range_header: str | None = Header(default=None, alias="Range"),
    api_key: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    expected_key = settings.API_KEY_DASHBOARD or settings.API_KEY_EDGE
    received_key = x_api_key or api_key
    if not received_key or not hmac.compare_digest(received_key, expected_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key invalida ou ausente.")

    try:
        stat = minio_db.stat_media(filename)
        total_size = stat.size
        content_type = stat.content_type or "application/octet-stream"

        start = 0
        end = total_size - 1
        status_code = status.HTTP_200_OK
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
        }

        if range_header:
            units, _, range_value = range_header.partition("=")
            if units != "bytes":
                raise HTTPException(status_code=416, detail="Range invalido.")

            start_text, _, end_text = range_value.partition("-")
            start = int(start_text) if start_text else 0
            end = int(end_text) if end_text else total_size - 1
            end = min(end, total_size - 1)

            if start > end or start >= total_size:
                raise HTTPException(status_code=416, detail="Range fora do ficheiro.")

            status_code = status.HTTP_206_PARTIAL_CONTENT
            headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"

        length = end - start + 1
        headers["Content-Length"] = str(length)
        response = minio_db.get_media_object(filename, offset=start, length=length)
        return StreamingResponse(
            _iter_minio_response(response),
            status_code=status_code,
            media_type=content_type,
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falha ao fazer stream de media: %s", filename)
        raise HTTPException(status_code=404, detail="Media nao encontrada ou indisponivel.") from exc
