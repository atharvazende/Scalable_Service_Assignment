from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

class OrderItemBase(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_id: int
    items: List[OrderItemBase]
    idempotency_key: str

class OrderItemResponse(BaseModel):
    product_id: int
    sku: str
    quantity: int
    unit_price: Decimal
    
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    order_id: int
    customer_id: int
    order_status: str
    payment_status: str
    order_total: Decimal
    created_at: datetime
    idempotency_key: Optional[str] = None
    totals_signature: Optional[str] = None
    items: List[OrderItemResponse]
    
    model_config = ConfigDict(from_attributes=True)
