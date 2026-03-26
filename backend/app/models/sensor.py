from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SensorData(BaseModel):
    sensor_id: str
    tipo: str          
    valor: float
    unidade: str       
    timestamp: Optional[datetime] = None
    