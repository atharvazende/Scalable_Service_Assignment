from sqlalchemy import Column, Integer, String, DateTime
from database import Base
import datetime

class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, index=True, nullable=False)
    carrier = Column(String, nullable=False)
    status = Column(String, default="PENDING") # PENDING, SHIPPED, DELIVERED, CANCELLED
    tracking_no = Column(String, unique=True, index=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
