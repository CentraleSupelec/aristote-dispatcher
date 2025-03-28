import json
import logging

from aio_pika import DeliveryMode, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)

from .exceptions import NoSuitableVllm, UnknownStrategy
from .metrics import DEFAULT_RETRY, stream_update_metrics
from .settings import settings
from .vllm_server import VLLMServer

# === Set constants ===

MODEL = settings.MODEL

RABBITMQ_URL = settings.RABBITMQ_URL

AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD
NB_REQUESTS_IN_QUEUE_THRESHOLD = settings.NB_REQUESTS_IN_QUEUE_THRESHOLD

RPC_RECONNECT_ATTEMPTS = settings.RPC_RECONNECT_ATTEMPTS
WAIT_FOR_LLM_DELAY = 1

VLLM_SERVERS = settings.VLLM_SERVERS

ROUTING_STRATEGY = settings.ROUTING_STRATEGY
LESS_BUSY = "less-busy"
ROUND_ROBIN = "round-robin"


class RPCServer:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.queue: AbstractQueue = None
        self.round_robin_idx = 0
        self.vllm_servers = settings.VLLM_SERVERS
        self.throughput_metrics = {
            vllm.url: {
                "last_generation_tokens_total": None,
                "last_update_timestamp": None,
                "first_update": True,
            }
            for vllm in self.vllm_servers
        }

    async def first_connect(self) -> None:
        logging.debug("Connecting consumer to RabbitMQ...")
        try:
            self.connection = await connect_robust(url=self.url)
            self.connection.reconnect_callbacks.add(self.reconnect_callback)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            self.queue = await self.channel.declare_queue(
                name=MODEL,
                durable=True,
                arguments={
                    "x-expires": settings.RPC_QUEUE_EXPIRATION,
                },
            )
            await self.queue.consume(
                self.on_message_callback,
                no_ack=True,
            )
        except Exception as e:
            logging.error("Error connecting to RabbitMQ: %s", e)
            raise
        else:
            logging.info("Consumer connected to RabbitMQ")

    async def reconnect_callback(self, connection: AbstractConnection) -> None:
        logging.info("Reconnecting to RabbitMQ...")
        self.connection = connection
        self.channel = await connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        self.queue = await self.channel.declare_queue(
            name=MODEL,
            durable=True,
            arguments={
                "x-expires": settings.RPC_QUEUE_EXPIRATION,
            },
        )
        await self.queue.consume(
            self.on_message_callback,
            no_ack=True,
        )
        logging.info("Reconnected to RabbitMQ")

    async def close(self) -> None:
        logging.debug("Closing RPC connection...")
        if await self.check_connection():
            try:
                await self.connection.close()
            except Exception as e:
                logging.error("Could not close RPC connection: %s", e)
            else:
                self.connection = None
                self.channel = None
                logging.info("RPC disconnected")

    async def find_first_available_server(
        self, retry: int = DEFAULT_RETRY
    ) -> VLLMServer:
        async for (
            current_avg_token,
            current_nb_users,
            current_nb_requests_in_queue,
            vllm_server,
            tasks,
        ) in stream_update_metrics(self.vllm_servers, self.throughput_metrics, retry):
            if current_nb_requests_in_queue <= NB_REQUESTS_IN_QUEUE_THRESHOLD and (
                current_avg_token >= AVG_TOKEN_THRESHOLD
                or current_nb_users <= NB_USER_THRESHOLD
            ):
                for task in tasks:
                    if not task.done():
                        task.cancel()
                return vllm_server

        raise NoSuitableVllm()

    async def on_message_callback(self, message: AbstractIncomingMessage):
        logging.debug("Message consumed on queue %s", MODEL)

        if ROUTING_STRATEGY == LESS_BUSY:
            vllm_server = await self.find_first_available_server(VLLM_SERVERS)
        elif (
            ROUTING_STRATEGY == ROUND_ROBIN
        ):  # elif for clarity but it's really an else, since ROUTING_STRATEGY is enforced to be either LESS_BUSY or ROUND_ROBIN
            vllm_server = VLLM_SERVERS[self.round_robin_idx]
            self.round_robin_idx = (self.round_robin_idx + 1) % len(VLLM_SERVERS)
        else:
            raise UnknownStrategy(ROUTING_STRATEGY)

        llm_params = {"llmUrl": vllm_server.url, "llmToken": vllm_server.token}

        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(llm_params).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=str(message.correlation_id),
                ),
                routing_key=message.reply_to,
            )
            logging.info("LLM URL for model %s sent to API", MODEL)
        except Exception as e:
            logging.error("An error occurred while publishing message: %s", e)
            raise

    async def check_connection(self) -> bool:
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False


rpc_server = RPCServer(url=RABBITMQ_URL)
