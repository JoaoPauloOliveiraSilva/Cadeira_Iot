from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    camera_id: str = Field(..., min_length=1, max_length=80)
    evento: Literal[
        "pessoa_detectada",
        "intruso_detectado",
        "som_suspeito",
        "movimento_suspeito",
        "outro",
    ]
    confianca: float = Field(..., ge=0, le=1)
    localizacao: str = Field(..., min_length=1, max_length=120)
    timestamp: datetime | None = None
    media_filename: str | None = Field(default=None, max_length=255)
    media_tipo: Literal["video", "image", "audio"] = "video"

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
