from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class InventoryItemResponse(BaseModel):
    inventory_id: int
    product_id: int
    warehouse: str
    on_hand: int
    reserved: int
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ReserveRequestItem(BaseModel):
    product_id: int
    quantity: int

class ReserveRequest(BaseModel):
    order_id: int
    items: List[ReserveRequestItem]

class ReleaseRequestItem(BaseModel):
    product_id: int
    quantity: int

class ReleaseRequest(BaseModel):
    order_id: int
    items: List[ReleaseRequestItem]

class ShipRequestItem(BaseModel):
    product_id: int
    quantity: int

class ShipRequest(BaseModel):
    order_id: int
    items: List[ShipRequestItem]
