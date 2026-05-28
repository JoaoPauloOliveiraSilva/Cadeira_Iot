from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import PurePath
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


client = Minio(
    settings.MINIO_URL,
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=settings.MINIO_SECURE,
)


def ensure_bucket_exists() -> None:
    found = client.bucket_exists(settings.MINIO_BUCKET)
    if not found:
        client.make_bucket(settings.MINIO_BUCKET)


def _safe_extension(filename: str | None, content_type: str | None) -> str:
    suffix = PurePath(filename or "").suffix.lower()
    allowed_suffixes = {".mp4", ".webm", ".jpg", ".jpeg", ".png", ".wav", ".mp3"}
    if suffix in allowed_suffixes:
        return suffix

    return {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
    }.get(content_type or "", ".bin")


def build_object_name(camera_id: str | None, filename: str | None, content_type: str | None) -> str:
    now = datetime.now(timezone.utc)
    camera = (camera_id or "unknown").replace("/", "_").replace("\\", "_")[:80]
    extension = _safe_extension(filename, content_type)
    return f"{camera}/{now:%Y/%m/%d}/{uuid4().hex}{extension}"


def upload_media(
    file_data: bytes,
    filename: str | None,
    content_type: str = "application/octet-stream",
    camera_id: str | None = None,
) -> str:
    ensure_bucket_exists()
    object_name = build_object_name(camera_id, filename, content_type)
    file_stream = BytesIO(file_data)

    try:
        client.put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            data=file_stream,
            length=len(file_data),
            content_type=content_type,
        )
        return object_name
    except S3Error as err:
        raise RuntimeError(f"Erro ao fazer upload para o MinIO: {err}") from err


def delete_media(object_name: str) -> None:
    try:
        client.remove_object(settings.MINIO_BUCKET, object_name)
    except S3Error:
        pass


def get_media_url(object_name: str, expires_minutes: int = 15) -> str:
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        expires=timedelta(minutes=expires_minutes),
    )


def stat_media(object_name: str):
    return client.stat_object(settings.MINIO_BUCKET, object_name)


def get_media_object(object_name: str, offset: int = 0, length: int | None = None):
    return client.get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        offset=offset,
        length=length,
    )
