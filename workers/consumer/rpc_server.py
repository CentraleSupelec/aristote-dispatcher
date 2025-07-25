import json
import logging

from aio_pika import DeliveryMode, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)

from .exceptions import ServerNotFound
from .priority_handler import BasePriorityHandler
from .quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy
from .settings import settings
from .strategy.server_selection_strategy import ServerSelectionStrategy

# === Set constants ===

MODEL = settings.MODEL


class RPCServer:
    def __init__(
        self,
        url: str,
        strategy: ServerSelectionStrategy,
        quality_of_service_policy: QualityOfServiceBasePolicy,
        priority_handler: BasePriorityHandler,
    ) -> None:
        self.url = url
        self.strategy = strategy
        self.quality_of_service_policy = quality_of_service_policy
        self.priority_handler = priority_handler
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.queue: AbstractQueue = None
        self.completion_queue: AbstractQueue = None
        self.current_parallel_requests: int = 0

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
                    "x-message-ttl": settings.RPC_MESSAGE_EXPIRATION,
                    "x-max-priority": settings.RPC_MAX_PRIORITY,
                },
            )
            await self.queue.consume(
                self.on_message_callback,
            )
            self.completion_queue = await self.channel.declare_queue(
                name=f"{MODEL}_completed",
                durable=True,
                arguments={
                    "x-expires": settings.RPC_QUEUE_EXPIRATION,
                },
            )
            await self.completion_queue.consume(
                self.on_completion_callback,
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
                "x-message-ttl": settings.RPC_MESSAGE_EXPIRATION,
                "x-max-priority": settings.RPC_MAX_PRIORITY,
            },
        )
        await self.queue.consume(
            self.on_message_callback,
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

    async def on_message_callback(self, message: AbstractIncomingMessage):
        logging.debug("Message consumed on queue %s", MODEL)

        try:
            vllm_server, performance_indicator = self.strategy.choose_server()
            priority = self.priority_handler.apply_priority(message.priority)
            if not self.quality_of_service_policy.apply_policy(
                performance_indicator, message, self.current_parallel_requests
            ):
                return
            llm_params = {"llmUrl": vllm_server.url, "llmToken": vllm_server.token}
            if priority is not None and isinstance(priority, int):
                llm_params["priority"] = priority
        except ServerNotFound:
            llm_params = {"llmUrl": "None", "llmToken": "None"}
        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(llm_params).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=str(message.correlation_id),
                ),
                routing_key=message.reply_to,
            )
            await message.ack()
            self.current_parallel_requests += 1
            logging.info("LLM URL for model %s sent to API", MODEL)
        except Exception as e:
            logging.error("An error occurred while publishing message: %s", e)
            raise

    async def on_completion_callback(self, message: AbstractIncomingMessage):
        try:
            data = json.loads(message.body.decode())
            logging.debug(
                "Completion received for message ID: %s, completed_at: %s",
                data.get("message_id"),
                data.get("completed_at"),
            )
            self.current_parallel_requests = max(self.current_parallel_requests - 1, 0)
            logging.debug(
                "self.current_parallel_requests = %s", self.current_parallel_requests
            )
            await message.ack()
        except Exception as e:
            logging.error("Error processing completion message: %s", e)

    async def check_connection(self) -> bool:
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False
