import os
import time
import logging
import asyncio
import re
from math import inf
from typing import MutableMapping
from httpx import AsyncClient
from aio_pika import connect, ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue, AbstractIncomingMessage

# TODO: Utiliser BaseSetting du module pydantic_settings
LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.INFO)) # CRITICAL = 50 / ERROR = 40 / WARNING = 30 / INFO = 20 / DEBUG = 10 / NOTSET = 0
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

MODEL = os.getenv("MODEL")
AVG_TOKEN_THRESHOLD = int(os.getenv("AVG_TOKEN_THRESHOLD", 7))
NB_USER_THRESHOLD = int(os.getenv("NB_USER_THRESHOLD", 10))
X_MAX_PRIORITY = int(os.getenv("X_MAX_PRIORITY", 5))
current_avg_token = inf
current_nb_users = 0

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", 5672)
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"

POD_NAME = os.getenv("POD_NAME", "localhost")
SERVICE_NAME = os.getenv("SERVICE_NAME", "")
TARGET_PORT = os.getenv("TARGET_PORT", 8080)
LLM_URL = os.getenv("LLM_URL", f"http://{POD_NAME}.{SERVICE_NAME}:{TARGET_PORT}")


async def try_connection(retry: int = 10):
    connection = None
    error = None
    duration = 0
    for i in range(retry):
        try:
            time.sleep(i)
            duration += i
            connection = await connect(url=RABBITMQ_URL)
            break
        except Exception as e:
            error = e
    if connection is None:
        error.add_note(f" [x] Failed to connect to rabbitMQ {retry} times in {duration} sec.")
        raise error
    return connection


class RPCClient:
    connection: AbstractConnection
    channel: AbstractChannel
    callback_queue: AbstractQueue

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}

    async def connect(self) -> None:
        self.connection = await connect(url=RABBITMQ_URL)
        self.channel = await self.connection.channel()
        self.callback_queue = await self.channel.declare_queue(exclusive=True)
        self.consumer_tag = await self.callback_queue.consume(self.on_response, no_ack=True)

    async def close(self) -> None:
        logging.info("Closing RPC Connection")
        await self.callback_queue.cancel(self.consumer_tag)
        await self.connection.close()
        logging.info("RPC Connection closed")

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            print(f"Bad message {message!r}")
            return

        future: asyncio.Future = self.futures.pop(message.correlation_id)
        future.set_result(message)

    async def call(self, routing_key: str, correlation_id: str) -> AbstractIncomingMessage:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        await self.channel.default_exchange.publish(
            message = Message(
                body=LLM_URL.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name
            ),
            routing_key=routing_key
        )
        logging.info(f"LLM URL for model {MODEL} sent to API")
        response: AbstractIncomingMessage = await future
        return response

async def update_metrics():
    global current_avg_token, current_nb_users
    line_pattern = r"^vllm:avg_generation_throughput_toks_per_s.*$"
    num_requests_running= r"^vllm:num_requests_running.*$"
    http_client = AsyncClient(base_url=LLM_URL)
    try:
        response = await http_client.request(method="GET", url="/metrics/")
    except Exception as e:
        logging.error("Impossible de récupérer les métrics du modèle")
        logging.exception(e)
        return 0
    # TODO: mieux gérer quand le LLM est pas dispo
    if response.status_code != 200:
        return -1, -1
    content = response.text
    tokens_per_second=float(re.search(line_pattern, content, re.MULTILINE).group(0).split(" ")[1])
    current_nb_users=float(re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1])
    if current_nb_users==0:
        current_avg_token=inf
    else:
        current_avg_token=tokens_per_second/current_nb_users
    logging.info("tokens_per_second %r" % tokens_per_second)
    logging.info("number_of_requests_running %r" % current_nb_users)
    logging.info("average_tokens_per_user %r" % current_avg_token)

async def on_message(message: AbstractIncomingMessage):
    global current_avg_token
    logging.info(f"Message consumed on queue {MODEL}")
    
    while current_avg_token < AVG_TOKEN_THRESHOLD and current_nb_users > NB_USER_THRESHOLD:
        await asyncio.sleep(.5)
        await update_metrics()

    # TODO: sortir rpcclient de la callback pour éviter d'ouvrir et fermer trop de connexions
    rpc_client = RPCClient()
    await rpc_client.connect()
    logging.info("RPC client connected")
    rpc_response = await rpc_client.call(
        routing_key=message.reply_to, 
        correlation_id=str(message.correlation_id)
    )
    await rpc_client.close()
    logging.info("RPC response received")
    await update_metrics()
    logging.info("Metrics updated")
    await message.ack()
    logging.info("Message ACK")

async def main():
    connection = await try_connection()
    logging.info("consumer connected")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    rpc_exchange = await channel.declare_exchange(
        name="rpc",
        type=ExchangeType.TOPIC,
        durable=True
    )
    model_queue = await channel.declare_queue(name=MODEL, durable=True)
    logging.info(f"queue {MODEL} declared")
    await model_queue.bind(exchange=rpc_exchange, routing_key=MODEL)
    logging.info("model queue binded to rpc exchange")
    await model_queue.consume(callback=on_message, no_ack=False)
    logging.info(f" [x] Consuming model queue: {MODEL}")
    await asyncio.Future()

if __name__=="__main__":
    logging.info(" [x] Starting consumer")
    # TODO: proprement fermé les connexions rabbitmq lorsque le script est arrêté
    asyncio.run(main())
