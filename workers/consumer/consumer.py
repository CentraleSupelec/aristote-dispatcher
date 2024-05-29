import os
import time
import logging
import asyncio 
import httpx
from aio_pika import connect, ExchangeType, IncomingMessage, Message, DeliveryMode
from aio_pika.exceptions import AMQPConnectionError

LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.INFO)) # CRITICAL = 50 / ERROR = 40 / WARNING = 30 / INFO = 20 / DEBUG = 10 / NOTSET = 0
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

TIMEOUT = int(os.getenv("TIMEOUT", 30))
X_MAX_PRIORITY = int(os.getenv("X_MAX_PRIORITY", 5))

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", 5672)
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"

POD_NAME = os.getenv("POD_NAME", "localhost")
SERVICE_NAME = os.getenv("SERVICE_NAME", "")
TARGET_PORT = os.getenv("TARGET_PORT", 8080)
SUFFIX = os.getenv("LLM_BASE_PATH", "/v1/chat/completions")
LLM_URL = os.getenv("LLM_URL", f"http://{POD_NAME}.{SERVICE_NAME}:{TARGET_PORT}{SUFFIX}")

async def try_connection(retry: int = 10):
    for i in range(retry):
        try:
            connection = await connect(url=RABBITMQ_URL)
            break
        except AMQPConnectionError:
            time.sleep(i)
    if connection is None:
        raise("Failed to connect to rabbitmq.")
    return connection

async def realtime_cb(message: IncomingMessage):
    logging.debug(" [x] Received message %r" % message)
    client = httpx.AsyncClient(verify=False)
    connection = await connect(url=RABBITMQ_URL)
    logging.debug(" [x] Connected")
    channel = await connection.channel()
    logging.debug(" [x] Channel 2 created")
    try:
        async with client.stream(
            method="POST",
            url=LLM_URL,
            content=message.body.decode(),
            timeout=TIMEOUT
        ) as response:
            logging.info(" [x] Response from source %r" % response)
            async for event in response.aiter_bytes():
                logging.debug(" [x] Event %r" % event)
                new_message = Message(body=event, delivery_mode=DeliveryMode.PERSISTENT)
                await channel.default_exchange.publish(
                    message=new_message,
                    routing_key=message.reply_to
                )
    except Exception as e:
        logging.error(e)
        error_message = Message(body=b"data: Internal error\n\n", delivery_mode=DeliveryMode.PERSISTENT)
        await channel.default_exchange.publish(
            message=error_message,
            routing_key=message.reply_to
        )
        
    await client.aclose()
    await connection.close()

async def main():
    connection = await try_connection()
    logging.info(" [x] Connected to RabbitMQ")
    channel = await connection.channel()
    logging.debug(" [x] Channel created")
    exchange = await channel.declare_exchange(
        name="rpc",
        type=ExchangeType.TOPIC,
        durable=True
    )
    logging.debug(" [x] Exchange declared")
    queue = await channel.declare_queue(
        name="real-time",
        durable=True,
        arguments={'x-max-priority': X_MAX_PRIORITY}
        )
    logging.debug(" [x] Queue declared")
    await queue.bind(
        exchange=exchange,
        routing_key="real-time.#"
    )
    logging.debug(" [x] Queue bound")
    await queue.consume(callback=realtime_cb, no_ack=True)
    logging.info(" [x] Consuming messages")
    await asyncio.Future()

if __name__=="__main__":
    logging.info(" [x] Starting consumer")
    asyncio.run(main())
