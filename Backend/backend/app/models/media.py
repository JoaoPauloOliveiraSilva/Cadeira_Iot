from datetime import datetime, timezone

from pydantic import BaseModel, Field


class MediaResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    upload_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    url: str | None = None
