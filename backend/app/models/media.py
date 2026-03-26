from pydantic import BaseModel
from datetime import datetime

class MediaResponse(BaseModel) :
    filename: str
    content_type: str
    size_bytes: int
    upload_at: datetime = datetime.now()
    url: str | None = None