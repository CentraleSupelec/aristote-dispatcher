import asyncio
import json
import logging
from typing import List

from aio_pika import DeliveryMode, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)
from metrics import DEFAULT_RETRY, stream_update_metrics
from settings import VLLMServer, settings

# === Set constants ===

MODEL = settings.MODEL

RABBITMQ_URL = settings.RABBITMQ_URL

AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD
NB_REQUESTS_IN_QUEUE_THRESHOLD = settings.NB_REQUESTS_IN_QUEUE_THRESHOLD

RPC_RECONNECT_ATTEMPTS = settings.RPC_RECONNECT_ATTEMPTS
WAIT_FOR_LLM_DELAY = 1


class RPCServer:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.queue: AbstractQueue = None

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
            logging.error(f"Error connecting to RabbitMQ: {e}")
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
                logging.error(f"Could not close RPC connection: {e}")
            else:
                self.connection = None
                self.channel = None
                logging.info("RPC disconnected")

    async def find_first_available_server(
        self, vllm_servers: List[VLLMServer], retry: int = DEFAULT_RETRY
    ) -> VLLMServer:
        async for (
            current_avg_token,
            current_nb_users,
            current_nb_requests_in_queue,
            vllm_server,
            tasks,
        ) in stream_update_metrics(vllm_servers, retry):
            if current_nb_requests_in_queue <= NB_REQUESTS_IN_QUEUE_THRESHOLD and (
                current_avg_token >= AVG_TOKEN_THRESHOLD
                or current_nb_users <= NB_USER_THRESHOLD
            ):
                for task in tasks:
                    if not task.done():
                        task.cancel()
                return vllm_server

        raise Exception("No suitable VLLM server found with good enough metrics")

    async def on_message_callback(self, message: AbstractIncomingMessage):
        logging.debug(f"Message consumed on queue {MODEL}")
        vllm_server = await self.find_first_available_server(settings.VLLM_SERVERS)

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
            logging.info(f"LLM URL for model {MODEL} sent to API")
        except Exception as e:
            logging.error(f"An error occurred while publishing message: {e}")
            raise

    async def check_connection(self) -> bool:
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False


rpc_server = RPCServer(url=RABBITMQ_URL)
