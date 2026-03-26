from pydantic import BaseModel
from typing import Optional      
from datetime import datetime

class AlertData(BaseModel):
    camera_id: str
    evento: str        
    confianca: float   
    localizacao: str
    timestamp: Optional[datetime] = None
    media_filename: str        
    media_tipo: Optional[str] = "video"
