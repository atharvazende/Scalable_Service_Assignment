from sqlalchemy import Column, Integer, String, DateTime, Numeric
from database import Base
import datetime

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, index=True, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(String, nullable=False)
    status = Column(String, default="PENDING") # SUCCESS, FAILED, REFUNDED
    reference = Column(String, unique=True, index=True)
    idempotency_key = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
