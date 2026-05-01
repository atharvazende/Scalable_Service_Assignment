from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List
import models
import schemas
from database import engine, Base, get_db
import utils
import asyncio
import os
import pika
import json
import datetime
from prometheus_client import Counter, Histogram

app = FastAPI(title="Inventory Service API", version="1.0.0")
utils.setup_common_app(app)

stockouts_total = Counter('stockouts_total', 'Total number of stockouts during reservation')
inventory_reserve_latency_ms = Histogram('inventory_reserve_latency_ms', 'Latency of inventory reservation')

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def publish_alert(message: dict):
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
        print(f"Failed to publish alert: {e}")

async def reservation_reaper():
    while True:
        await asyncio.sleep(60)  # Run every minute
        try:
            from database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                # Find RESERVE movements older than 15 mins without RELEASE/SHIP
                cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
                result = await session.execute(
                    select(models.InventoryMovement)
                    .where(models.InventoryMovement.type == "RESERVE")
                    .where(models.InventoryMovement.created_at < cutoff)
                )
                reserves = result.scalars().all()
                for res in reserves:
                    # Check if already released or shipped
                    chk = await session.execute(
                        select(models.InventoryMovement)
                        .where(models.InventoryMovement.order_id == res.order_id)
                        .where(models.InventoryMovement.type.in_(["RELEASE", "SHIP"]))
                    )
                    if not chk.scalars().first():
                        # Release it
                        inv_res = await session.execute(
                            select(models.Inventory)
                            .where(models.Inventory.product_id == res.product_id)
                            .where(models.Inventory.warehouse == res.warehouse)
                        )
                        inv = inv_res.scalars().first()
                        if inv:
                            inv.reserved -= res.quantity
                        
                        rel_movement = models.InventoryMovement(
                            product_id=res.product_id,
                            warehouse=res.warehouse,
                            order_id=res.order_id,
                            type="RELEASE",
                            quantity=res.quantity,
                            created_at=datetime.datetime.utcnow()
                        )
                        session.add(rel_movement)
                await session.commit()
        except Exception as e:
            print(f"Reaper error: {e}")
utils.setup_common_app(app)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    asyncio.create_task(reservation_reaper())

@app.get("/v1/inventory/{product_id}", response_model=List[schemas.InventoryItemResponse])
async def get_inventory(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Inventory).where(models.Inventory.product_id == product_id))
    return result.scalars().all()

@app.post("/v1/inventory/reserve")
async def reserve_inventory(request: schemas.ReserveRequest, db: AsyncSession = Depends(get_db)):
    # Check if this order_id already has a reserve movement (Idempotency)
    existing_movement = await db.execute(
        select(models.InventoryMovement)
        .where(models.InventoryMovement.order_id == request.order_id)
        .where(models.InventoryMovement.type == "RESERVE")
    )
    if existing_movement.scalars().first():
        return {"status": "success", "message": "Already reserved"}

    # Validate all items first
    allocations = []
    for item in request.items:
        result = await db.execute(
            select(models.Inventory)
            .where(models.Inventory.product_id == item.product_id)
        )
        inventories = result.scalars().all()
        
        qty_needed = item.quantity
        item_allocations = []
        for inv in inventories:
            available = inv.on_hand - inv.reserved
            if available > 0:
                take = min(qty_needed, available)
                item_allocations.append((inv, take))
                qty_needed -= take
            if qty_needed == 0:
                break
                
        if qty_needed > 0:
            stockouts_total.inc()
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product_id: {item.product_id}")
            
        allocations.extend(item_allocations)
        
    # Execute reservations
    for inv, take in allocations:
        inv.reserved += take
        movement = models.InventoryMovement(
            product_id=inv.product_id,
            warehouse=inv.warehouse,
            order_id=request.order_id,
            type="RESERVE",
            quantity=take
        )
        db.add(movement)
        
        # Low stock alert check
        if (inv.on_hand - inv.reserved) < 10:
            publish_alert({
                "type": "LOW_STOCK",
                "product_id": inv.product_id,
                "warehouse": inv.warehouse,
                "available": inv.on_hand - inv.reserved
            })
            
    await db.commit()
    return {"status": "success"}

@app.post("/v1/inventory/release")
async def release_inventory(request: schemas.ReleaseRequest, db: AsyncSession = Depends(get_db)):
    # Find the RESERVATION movements for this order
    movements = await db.execute(
        select(models.InventoryMovement)
        .where(models.InventoryMovement.order_id == request.order_id)
        .where(models.InventoryMovement.type == "RESERVE")
    )
    reserves = movements.scalars().all()
    
    if not reserves:
        return {"status": "success", "message": "No reservations found to release"}
        
    # Check if already released
    released = await db.execute(
        select(models.InventoryMovement)
        .where(models.InventoryMovement.order_id == request.order_id)
        .where(models.InventoryMovement.type == "RELEASE")
    )
    if released.scalars().first():
        return {"status": "success", "message": "Already released"}

    for res in reserves:
        # Find inventory and reduce reserved
        inv_result = await db.execute(
            select(models.Inventory)
            .where(models.Inventory.product_id == res.product_id)
            .where(models.Inventory.warehouse == res.warehouse)
        )
        inv = inv_result.scalars().first()
        if inv:
            inv.reserved -= res.quantity
            
        rel_movement = models.InventoryMovement(
            product_id=res.product_id,
            warehouse=res.warehouse,
            order_id=request.order_id,
            type="RELEASE",
            quantity=res.quantity
        )
        db.add(rel_movement)
        
    await db.commit()
    return {"status": "success"}

@app.post("/v1/inventory/ship")
async def ship_inventory(request: schemas.ShipRequest, db: AsyncSession = Depends(get_db)):
    # Find reservations
    movements = await db.execute(
        select(models.InventoryMovement)
        .where(models.InventoryMovement.order_id == request.order_id)
        .where(models.InventoryMovement.type == "RESERVE")
    )
    reserves = movements.scalars().all()
    
    if not reserves:
         raise HTTPException(status_code=400, detail="Cannot ship without prior reservation")
         
    # Idempotency check
    shipped = await db.execute(
        select(models.InventoryMovement)
        .where(models.InventoryMovement.order_id == request.order_id)
        .where(models.InventoryMovement.type == "SHIP")
    )
    if shipped.scalars().first():
        return {"status": "success", "message": "Already shipped"}

    for res in reserves:
        inv_result = await db.execute(
            select(models.Inventory)
            .where(models.Inventory.product_id == res.product_id)
            .where(models.Inventory.warehouse == res.warehouse)
        )
        inv = inv_result.scalars().first()
        if inv:
            # converting reserved to shipped (deduct from both)
            inv.reserved -= res.quantity
            inv.on_hand -= res.quantity
            
        ship_movement = models.InventoryMovement(
            product_id=res.product_id,
            warehouse=res.warehouse,
            order_id=request.order_id,
            type="SHIP",
            quantity=res.quantity
        )
        db.add(ship_movement)
        
    await db.commit()
    return {"status": "success"}
