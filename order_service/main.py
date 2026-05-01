from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import models
import schemas
from database import engine, Base, get_db
import httpx
import os
import json
import pika
import utils

app = FastAPI(title="Order Service API", version="1.0.0")
utils.setup_common_app(app)

CATALOG_URL = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8001")
INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8002")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8004")
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

import hashlib
import decimal
from prometheus_client import Counter

orders_placed_total = Counter('orders_placed_total', 'Total number of orders placed')

@app.post("/v1/orders", response_model=schemas.OrderResponse)
async def create_order(order_req: schemas.OrderCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # 0. Idempotency Check
    existing = await db.execute(select(models.Order).where(models.Order.idempotency_key == order_req.idempotency_key))
    existing_order = existing.scalars().first()
    if existing_order:
        result = await db.execute(
            select(models.Order).where(models.Order.order_id == existing_order.order_id).options(selectinload(models.Order.items))
        )
        return result.scalars().first()

    # 1. Fetch prices from Catalog Service
    items_data = []
    total_amount = decimal.Decimal(0)
    async with httpx.AsyncClient() as client:
        for item in order_req.items:
            try:
                resp = await client.get(f"{CATALOG_URL}/v1/products/{item.product_id}")
                resp.raise_for_status()
                product = resp.json()
                price = decimal.Decimal(str(product['price']))
                items_data.append({
                    "product_id": item.product_id,
                    "sku": product['sku'],
                    "quantity": item.quantity,
                    "unit_price": price
                })
                total_amount += price * decimal.Decimal(item.quantity)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to fetch product {item.product_id} from catalog")

    # Add 5% tax and flat 10 shipping
    total_amount = total_amount + (total_amount * decimal.Decimal("0.05")) + decimal.Decimal("10.0")
    
    # Banker's Rounding to 2 decimal places
    total_amount = total_amount.quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_EVEN)
    
    # Generate Totals Signature (hash)
    signature_data = f"{total_amount}_{order_req.customer_id}_{order_req.idempotency_key}"
    totals_signature = hashlib.sha256(signature_data.encode()).hexdigest()

    # 2. Save Order to DB as PENDING
    new_order = models.Order(
        customer_id=order_req.customer_id,
        order_status="PENDING",
        payment_status="PENDING",
        order_total=total_amount,
        idempotency_key=order_req.idempotency_key,
        totals_signature=totals_signature
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    for item_data in items_data:
        order_item = models.OrderItem(
            order_id=new_order.order_id,
            product_id=item_data['product_id'],
            sku=item_data['sku'],
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price']
        )
        db.add(order_item)
    await db.commit()

    # 3. Reserve Inventory
    async with httpx.AsyncClient() as client:
        reserve_payload = {
            "order_id": new_order.order_id,
            "items": [{"product_id": item.product_id, "quantity": item.quantity} for item in order_req.items]
        }
        try:
            inv_resp = await client.post(f"{INVENTORY_URL}/v1/inventory/reserve", json=reserve_payload)
            inv_resp.raise_for_status()
        except Exception as e:
            # Reserve failed
            new_order.order_status = "CANCELLED"
            await db.commit()
            raise HTTPException(status_code=400, detail="Inventory reservation failed due to stock out")

    # 4. Charge Payment
    SHIPPING_URL = os.getenv("SHIPPING_SERVICE_URL", "http://localhost:8005")
    async with httpx.AsyncClient() as client:
        payment_payload = {
            "order_id": new_order.order_id,
            "amount": float(total_amount),
            "method": "CREDIT_CARD",
            "idempotency_key": f"order_{new_order.order_id}"
        }
        try:
            pay_resp = await client.post(f"{PAYMENT_URL}/v1/payments/charge", json=payment_payload)
            pay_resp.raise_for_status()
            
            # Payment Success
            new_order.order_status = "CONFIRMED"
            new_order.payment_status = "PAID"
            orders_placed_total.inc()
            await db.commit()
            
            # 5. Optional Call to Shipping Service
            try:
                ship_payload = {"order_id": new_order.order_id, "carrier": "FedEx"}
                await client.post(f"{SHIPPING_URL}/v1/shipments", json=ship_payload)
            except Exception as ship_ex:
                print(f"Shipping call failed: {ship_ex}")
            
            # Publish notification
            background_tasks.add_task(publish_notification, {
                "type": "ORDER_CONFIRMED",
                "order_id": new_order.order_id,
                "customer_id": new_order.customer_id
            })
            
        except Exception as e:
            # Payment Failed -> Release Inventory
            new_order.order_status = "CANCELLED"
            new_order.payment_status = "FAILED"
            await db.commit()
            
            # Async release
            await client.post(f"{INVENTORY_URL}/v1/inventory/release", json=reserve_payload)
            
            raise HTTPException(status_code=400, detail="Payment failed. Order cancelled and inventory released.")

    await db.refresh(new_order)
    result = await db.execute(
        select(models.Order).where(models.Order.order_id == new_order.order_id).options(selectinload(models.Order.items))
    )
    return result.scalars().first()

@app.get("/v1/orders/{order_id}", response_model=schemas.OrderResponse)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Order).where(models.Order.order_id == order_id).options(selectinload(models.Order.items))
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.post("/v1/orders/{order_id}/refund")
async def refund_order(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Order).where(models.Order.order_id == order_id).options(selectinload(models.Order.items)))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.order_status = "CANCELLED"
    order.payment_status = "REFUNDED"
    await db.commit()
    
    # Release inventory
    async with httpx.AsyncClient() as client:
        reserve_payload = {
            "order_id": order_id,
            "items": [{"product_id": item.product_id, "quantity": item.quantity} for item in order.items]
        }
        try:
            await client.post(f"{INVENTORY_URL}/v1/inventory/release", json=reserve_payload)
        except Exception as e:
            print(f"Failed to release inventory on refund: {e}")
            
    return {"status": "refunded"}
