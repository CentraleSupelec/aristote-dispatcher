import asyncio
import logging
import re
import signal

from aio_pika import connect, ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from httpx import AsyncClient
from math import inf
from rpc import RPCClient
from settings import settings


# === Set constants ===

MODEL = settings.MODEL
AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD

RABBITMQ_URL = settings.RABBITMQ_URL
LLM_URL = settings.LLM_URL

DEFAULT_RETRY = 10
WAIT_TIME = 0.5


# === Initialize global variables ==

current_avg_token = inf
current_nb_users = 0

shutdown_signal = asyncio.Event()


# === Utility functions ===

async def try_connection(retry: int = DEFAULT_RETRY):
    for attempt in range(retry):
        try:
            await asyncio.sleep(attempt)
            return await connect(url=RABBITMQ_URL)
        except Exception as e:
            logging.debug(f"Attempt {attempt+1}/{retry} to connect consumer to RabbitMQ failed : {e}")
    logging.error(f"Failed to connect consumer to RabbitMQ after {retry} attempts")
    raise Exception(f"Failed to connect consumer to RabbitMQ after {retry} attempts")

async def update_metrics():
    global current_avg_token, current_nb_users

    async with AsyncClient(base_url=LLM_URL) as http_client:
        try:
            response = await http_client.get("/metrics/")
            response.raise_for_status()
        except Exception as e:
            logging.error("Failed to update model metrics: {e}")
            raise
    
    content = response.text

    line_pattern = r"^vllm:avg_generation_throughput_toks_per_s.*$"
    num_requests_running = r"^vllm:num_requests_running.*$"

    tokens_per_second = float(re.search(line_pattern, content, re.MULTILINE).group(0).split(" ")[1])
    current_nb_users = float(re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1])
    current_avg_token = tokens_per_second/current_nb_users if current_nb_users else inf

    logging.debug(f" > [Metrics] Tokens per second: {tokens_per_second}")
    logging.debug(f" > [Metrics] Running requests: {current_nb_users}")
    logging.debug(f" > [Metrics] Average token per user: {current_avg_token}")

async def try_update_metrics(retry: int = DEFAULT_RETRY):
    for attempt in range(retry):
        try:
            await update_metrics()
            return
        except Exception:
            logging.debug(f"Attempt {attempt+1}/{retry} to update model metrics failed")
            await asyncio.sleep(attempt)
    logging.error(f"Failed to update model metrics atfer {retry} attempts")
    raise Exception(f"Failed to update model metrics atfer {retry} attempts")

async def on_message(message: AbstractIncomingMessage, rpc_client: RPCClient):
    global current_avg_token

    logging.info(f"Message consumed on queue {MODEL}")
    
    while current_avg_token < AVG_TOKEN_THRESHOLD and current_nb_users > NB_USER_THRESHOLD:
        await asyncio.sleep(WAIT_TIME)
        await try_update_metrics()

    rpc_response = await rpc_client.call(
        routing_key=message.reply_to, 
        correlation_id=str(message.correlation_id)
    )
    
    logging.info("RPC response received")
    await try_update_metrics()
    logging.info("Metrics updated")
    await message.ack()
    logging.info("Message ACK")


# === Main function ===

async def main():
    logging.debug("Connecting consumer to RabbitMQ...")
    connection = await try_connection()
    logging.info("Consumer connected to RabbitMQ")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    rpc_exchange = await channel.declare_exchange(
        name="rpc",
        type=ExchangeType.TOPIC,
        durable=True
    )
    model_queue = await channel.declare_queue(name=MODEL, durable=True)
    logging.info(f"Queue {MODEL} declared on channel")
    await model_queue.bind(exchange=rpc_exchange, routing_key=MODEL)
    logging.info("Queue binded to RPC channel")
    
    rpc_client = RPCClient(url=RABBITMQ_URL)
    logging.debug("Connecting to RPC...")
    await rpc_client.connect()
    logging.info("Client connected to RPC")

    await model_queue.consume(
        callback = lambda message: on_message(message, rpc_client),
        no_ack=False
    )
    logging.info(f" [x] Consumption of queue {MODEL}")
    
    await shutdown_signal.wait()

    logging.debug("Closing RPC connection...")
    await rpc_client.close()
    logging.debug("RPC disconnect")
    logging.debug("Closing consumer connection...")
    await connection.close()
    logging.info(" [x] Consumer connection closed")


# === Entry point ===

if __name__=="__main__":
    logging.info(" [x] Starting consumer")

    def shutdown():
        logging.info(" [x] Shutting down consumer...")
        shutdown_signal.set()

    asyncio.set_event_loop(asyncio.new_event_loop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
