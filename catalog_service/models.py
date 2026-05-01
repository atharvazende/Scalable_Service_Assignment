from sqlalchemy import Column, Integer, String, Numeric, Boolean
from database import Base

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)
