import asyncio
import logging
import re
import signal
from math import inf
from typing import MutableMapping

from aio_pika import connect, ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue, AbstractIncomingMessage
from httpx import AsyncClient
from settings import Settings


# === Import settings from settings.py ===

settings = Settings()


# === Set constants ===

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

MODEL = settings.MODEL
AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD
X_MAX_PRIORITY = settings.X_MAX_PRIORITY

RABBITMQ_URL = settings.RABBITMQ_URL
LLM_URL = settings.LLM_URL

DEFAULT_RETRY = 10
WAIT_TIME = 0.5

HTTP_OK = 200


# === Initialize global variables ==

current_avg_token = inf
current_nb_users = 0

shutdown_signal = asyncio.Event()


async def try_connection(retry: int = DEFAULT_RETRY):
    for attempt in range(retry):
        try:
            await asyncio.sleep(attempt)
            return await connect(url=RABBITMQ_URL)
        except Exception as e:
            error = e
    raise Exception(f"Failed to connect to RabbitMQ after {retry} attempts.") from error


class RPCClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.callback_queue: AbstractQueue = None
        self.futures: MutableMapping[str, asyncio.Future] = {}

    async def connect(self) -> None:
        self.connection = await connect(url=self.url)
        self.channel = await self.connection.channel()
        self.callback_queue = await self.channel.declare_queue(exclusive=True)
        self.consumer_tag = await self.callback_queue.consume(self.on_response, no_ack=True)

    async def close(self) -> None:
        logging.info("Closing RPC Connection...")
        await self.callback_queue.cancel(self.consumer_tag)
        await self.connection.close()
        logging.info("RPC Connection closed")

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        logging.info(f"Received message with correlation_id: {message.correlation_id}")
        if message.correlation_id:
            future = self.futures.pop(message.correlation_id, None)
            if future:
                future.set_result(message)
                logging.info(f"Future for correlation_id {message.correlation_id} has been set")
            else:
                logging.error(f"No future found for correlation_id {message.correlation_id}")
        else:
            logging.error(f"Received message without correlation_id: {message!r}")

    async def call(self, routing_key: str, correlation_id: str) -> AbstractIncomingMessage:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        await self.channel.default_exchange.publish(
            Message(
                body=LLM_URL.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name
            ),
            routing_key
        )
        logging.info(f"LLM URL for model {MODEL} sent to API")
        return await future

async def update_metrics():
    global current_avg_token, current_nb_users

    async with AsyncClient(base_url=LLM_URL) as http_client:
        try:
            response = await http_client.get("/metrics/")
            response.raise_for_status()
        except Exception as e:
            logging.error("Impossible de récupérer les métrics du modèle")
            logging.exception(e)
            return -1, -1
    
    content = response.text

    line_pattern = r"^vllm:avg_generation_throughput_toks_per_s.*$"
    num_requests_running= r"^vllm:num_requests_running.*$"

    tokens_per_second=float(re.search(line_pattern, content, re.MULTILINE).group(0).split(" ")[1])
    current_nb_users=float(re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1])
    current_avg_token = tokens_per_second / current_nb_users if current_nb_users else inf

    logging.info("tokens_per_second %r" % tokens_per_second)
    logging.info("number_of_requests_running %r" % current_nb_users)
    logging.info("average_tokens_per_user %r" % current_avg_token)

    return current_avg_token, current_nb_users

async def on_message(message: AbstractIncomingMessage, rpc_client: RPCClient):
    global current_avg_token

    logging.info(f"Message consumed on queue {MODEL}")
    
    while current_avg_token < AVG_TOKEN_THRESHOLD and current_nb_users > NB_USER_THRESHOLD:
        await asyncio.sleep(WAIT_TIME)
        await update_metrics()

    rpc_response = await rpc_client.call(
        routing_key=message.reply_to, 
        correlation_id=str(message.correlation_id)
    )
    
    logging.info("RPC response received")
    await update_metrics()
    logging.info("Metrics updated")
    await message.ack()
    logging.info("Message ACK")

async def main():
    connection = await try_connection()
    logging.info("Consumer connected")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    rpc_exchange = await channel.declare_exchange(
        name="rpc",
        type=ExchangeType.TOPIC,
        durable=True
    )
    model_queue = await channel.declare_queue(name=MODEL, durable=True)
    logging.info(f"Queue {MODEL} declared")
    await model_queue.bind(exchange=rpc_exchange, routing_key=MODEL)
    logging.info("Model queue binded to RPC exchange")
    
    rpc_client = RPCClient(url=RABBITMQ_URL)
    await rpc_client.connect()
    logging.info("RPC client connected")

    await model_queue.consume(
        callback = lambda message: on_message(message, rpc_client),
        no_ack=False
    )
    logging.info(f" [x] Consuming model queue: {MODEL}")
    
    await shutdown_signal.wait()

    await rpc_client.close()
    await connection.close()
    logging.info(" [x] Consumer closed")

if __name__=="__main__":
    logging.info(" [x] Starting consumer")

    def shutdown():
        logging.info(" [x] Consumer shutting down")
        shutdown_signal.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
