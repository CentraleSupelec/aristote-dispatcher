import asyncio
import json
import logging
import uuid
from enum import Enum
from typing import MutableMapping, Union

from aio_pika import DeliveryMode, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)

from src.sender.settings import Settings


class CallResult(Enum):
    SUCCESS = 0
    QUEUE_OVERLOADED = 1001
    TIMEOUT = 1002


class RPCClient:
    def __init__(self, settings: Settings) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.settings = settings
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.callback_queue: AbstractQueue = None
        self.consumer_tag = None

    async def first_connect(self) -> None:
        logging.debug("Connecting sender to RabbitMQ...")
        try:
            self.connection = await connect_robust(url=self.settings.RABBITMQ_URL)
            self.connection.reconnect_callbacks.add(self.reconnect_callback)
            self.channel = await self.connection.channel()
            self.callback_queue = await self.channel.declare_queue(exclusive=True)
            self.consumer_tag = await self.callback_queue.consume(
                self.on_response, no_ack=True
            )
        except Exception as e:
            logging.error("Error connecting to RabbitMQ: %s", e)
            raise
        else:
            logging.info("Sender connected to RabbitMQ")

    async def reconnect_callback(self, connection: AbstractConnection) -> None:
        logging.info("Reconnecting to RabbitMQ...")
        self.connection = connection
        self.channel = await connection.channel()
        self.callback_queue = await self.channel.declare_queue(exclusive=True)
        self.consumer_tag = await self.callback_queue.consume(
            self.on_response, no_ack=True
        )
        logging.info("Reconnected to RabbitMQ")

    async def close(self) -> None:
        logging.debug("Closing RPC Connection...")
        if await self.check_connection():
            try:
                await self.callback_queue.cancel(self.consumer_tag)
                await self.connection.close()
            except Exception as e:
                logging.error("Could not close connection: %s", e)
            else:
                logging.info("RPC Connection closed")
                self.connection = None
                self.channel = None

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            logging.error("Bad message received %r. Missing correlation_id.", message)
            return

        future: asyncio.Future = self.futures.pop(message.correlation_id)
        logging.info("Received response.")
        logging.debug(" > Response body: %s", message.body)
        future.set_result(message)

    async def call(
        self,
        priority: int,
        threshold: int,
        model: str,
        organization: str,
        routing_mode: str,
    ) -> Union[AbstractIncomingMessage, CallResult]:
        model_queue = await self.channel.get_queue(name=model)
        nb_messages = model_queue.declaration_result.message_count
        logging.debug("%s messages in the model queue : %s", nb_messages, model)
        if nb_messages > threshold:
            return CallResult.QUEUE_OVERLOADED

        logging.info("New request for model %s", model)
        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        if routing_mode == "any":
            await self.channel.default_exchange.publish(
                message=Message(
                    body=b"AVAILABLE?",
                    headers={"x-requeue-count": 0},
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=correlation_id,
                    reply_to=self.callback_queue.name,
                    priority=priority,
                ),
                routing_key=model,
            )
            logging.debug("Message pushed to model queue %s", model)

        else:
            payload = {
                "routing_mode": routing_mode,
                "organization": organization,
            }
            await self.channel.default_exchange.publish(
                message=Message(
                    body=json.dumps(payload).encode("utf-8"),
                    headers={"x-requeue-count": 0},
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=correlation_id,
                    reply_to=self.callback_queue.name,
                    priority=priority,
                ),
                routing_key=f"{model}_{organization}_private",
            )
            logging.debug("Message pushed to model queue %s %s", model, organization)
        try:
            response = await asyncio.wait_for(
                future, timeout=self.settings.MESSAGE_TIMEOUT
            )  # Timeout in seconds
            logging.info("Received URL for model %s", model)
            return response
        except asyncio.TimeoutError:
            self.futures.pop(correlation_id, None)  # Clean up
            logging.warning("Timeout waiting for response from consumer")
            return CallResult.TIMEOUT

    async def send_completion_message(self, model: str, payload: dict) -> None:
        try:
            routing_key = f"{model}_completed"
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(payload).encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT,
                ),
                routing_key=routing_key,
            )
            logging.debug(
                "Sent completion message to %s  (id: %s)",
                routing_key,
                payload.get("message_id", "ID NOT FOUND"),
            )
        except Exception as e:
            logging.error("Failed to send completion message: %s", e)

    async def check_connection(self):
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False
