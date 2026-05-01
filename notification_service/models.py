from sqlalchemy import Column, Integer, String, DateTime
from database import Base
import datetime

class NotificationLog(Base):
    __tablename__ = "notifications_log"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False) # ORDER_CONFIRMED, SHIPMENT_UPDATE
    recipient = Column(String, nullable=True)
    message = Column(String, nullable=False)
    status = Column(String, default="SENT")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
