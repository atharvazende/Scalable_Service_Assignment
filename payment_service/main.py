from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models
import schemas
from database import engine, Base, get_db
import uuid
import random
import utils
import httpx
import os
from prometheus_client import Counter

app = FastAPI(title="Payment Service API", version="1.0.0")
utils.setup_common_app(app)

payments_failed_total = Counter('payments_failed_total', 'Total number of failed payments')
ORDER_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8003")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post("/v1/payments/charge", response_model=schemas.PaymentResponse)
async def charge_payment(request: schemas.ChargeRequest, db: AsyncSession = Depends(get_db)):
    # 1. Idempotency Check
    existing_payment = await db.execute(
        select(models.Payment).where(models.Payment.idempotency_key == request.idempotency_key)
    )
    payment = existing_payment.scalars().first()
    if payment:
        return payment

    # 2. Simulate Payment Gateway Processing
    # Introduce a 10% chance of failure for realistic testing
    is_success = random.random() > 0.1
    
    new_payment = models.Payment(
        order_id=request.order_id,
        amount=request.amount,
        method=request.method,
        status="SUCCESS" if is_success else "FAILED",
        reference=f"REF_{uuid.uuid4().hex[:8].upper()}",
        idempotency_key=request.idempotency_key
    )
    db.add(new_payment)
    await db.commit()
    await db.refresh(new_payment)
    
    if not is_success:
        payments_failed_total.inc()
        raise HTTPException(status_code=400, detail="Payment declined by gateway")
        
    return new_payment

@app.post("/v1/payments/{payment_id}/refund", response_model=schemas.PaymentResponse)
async def refund_payment(payment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Payment).where(models.Payment.payment_id == payment_id))
    payment = result.scalars().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    if payment.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Can only refund successful payments")
        
    payment.status = "REFUNDED"
    await db.commit()
    await db.refresh(payment)
    
    # Call order service to refund
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{ORDER_URL}/v1/orders/{payment.order_id}/refund")
        except Exception as e:
            print(f"Failed to call order service for refund: {e}")
            
    return payment
