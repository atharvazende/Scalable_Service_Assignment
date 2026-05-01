from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class ProductBase(BaseModel):
    sku: str
    name: str
    category: Optional[str] = None
    price: Decimal
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[Decimal] = None
    is_active: Optional[bool] = None

class ProductResponse(ProductBase):
    product_id: int
    
    model_config = ConfigDict(from_attributes=True)
