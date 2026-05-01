from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ShipmentCreate(BaseModel):
    order_id: int
    carrier: str

class ShipmentUpdate(BaseModel):
    status: str

class ShipmentResponse(BaseModel):
    shipment_id: int
    order_id: int
    carrier: str
    status: str
    tracking_no: str
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)
