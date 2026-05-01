from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime

class ChargeRequest(BaseModel):
    order_id: int
    amount: Decimal
    method: str
    idempotency_key: str

class PaymentResponse(BaseModel):
    payment_id: int
    order_id: int
    amount: Decimal
    method: str
    status: str
    reference: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
