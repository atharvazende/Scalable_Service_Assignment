from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models
import schemas
from database import engine, Base, get_db
import uuid
import datetime
import pika
import json
import os
import utils

app = FastAPI(title="Shipping Service API", version="1.0.0")
utils.setup_common_app(app)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def publish_notification(message: dict):
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='notifications', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='notifications',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        print(f"Failed to publish notification: {e}")

@app.post("/v1/shipments", response_model=schemas.ShipmentResponse, status_code=201)
async def create_shipment(request: schemas.ShipmentCreate, db: AsyncSession = Depends(get_db)):
    new_shipment = models.Shipment(
        order_id=request.order_id,
        carrier=request.carrier,
        tracking_no=f"TRK{uuid.uuid4().hex[:10].upper()}",
        status="PENDING"
    )
    db.add(new_shipment)
    await db.commit()
    await db.refresh(new_shipment)
    return new_shipment

@app.put("/v1/shipments/{shipment_id}", response_model=schemas.ShipmentResponse)
async def update_shipment(shipment_id: int, request: schemas.ShipmentUpdate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Shipment).where(models.Shipment.shipment_id == shipment_id))
    shipment = result.scalars().first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
        
    shipment.status = request.status
    if request.status == "SHIPPED":
        shipment.shipped_at = datetime.datetime.utcnow()
    elif request.status == "DELIVERED":
        shipment.delivered_at = datetime.datetime.utcnow()
        
    await db.commit()
    await db.refresh(shipment)
    
    # Notify shipment update
    background_tasks.add_task(publish_notification, {
        "type": "SHIPMENT_UPDATE",
        "order_id": shipment.order_id,
        "tracking_no": shipment.tracking_no,
        "status": shipment.status
    })
    
    return shipment
