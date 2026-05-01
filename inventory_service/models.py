from sqlalchemy import Column, Integer, String, DateTime
from database import Base
import datetime

class Inventory(Base):
    __tablename__ = "inventory"

    inventory_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, index=True, nullable=False)
    warehouse = Column(String, index=True, nullable=False)
    on_hand = Column(Integer, default=0)
    reserved = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    movement_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, index=True, nullable=False)
    warehouse = Column(String, index=True, nullable=False)
    order_id = Column(Integer, index=True, nullable=True)
    type = Column(String, nullable=False) # RESERVE, RELEASE, SHIP
    quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
