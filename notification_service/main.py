from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from database import engine, Base, AsyncSessionLocal
import models
import asyncio
import pika
import json
import os
import logging
import sys

import logging
import sys
import utils

logger = logging.getLogger("notification_service")

app = FastAPI(title="Notification Service API", version="1.0.0")
utils.setup_common_app(app)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

async def process_message(message: dict):
    # Mask sensitive data before logging
    if "customer_id" in message:
        # If we had email/phone, we would mask it here
        pass
        
    log_msg = json.dumps(message)
    logger.info(log_msg)
    
    # Save to DB
    async with AsyncSessionLocal() as session:
        log_entry = models.NotificationLog(
            type=message.get("type", "UNKNOWN"),
            message=json.dumps(message)
        )
        session.add(log_entry)
        await session.commit()

def consume_messages():
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='notifications', durable=True)

        def callback(ch, method, properties, body):
            try:
                message = json.loads(body)
                # Process async in sync callback
                asyncio.run(process_message(message))
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f'{{"error": "Failed to process message", "details": "{str(e)}"}}')

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='notifications', on_message_callback=callback)
        channel.start_consuming()
    except Exception as e:
        logger.error(f'{{"error": "RabbitMQ connection failed", "details": "{str(e)}"}}')

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Start consumer in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, consume_messages)

