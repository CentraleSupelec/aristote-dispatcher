import asyncio
import logging
import uuid
from typing import MutableMapping

from aio_pika import DeliveryMode, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)
from settings import Settings


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
            logging.error(f"Error connecting to RabbitMQ: {e}")
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
                logging.error(f"Could not close connection: {e}")
            else:
                logging.info("RPC Connection closed")
                self.connection = None
                self.channel = None

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            logging.error(f"Bad message received {message!r}. Missing correlation_id.")
            return

        future: asyncio.Future = self.futures.pop(message.correlation_id)
        logging.info(f"Received response.")
        logging.debug(f" > Response body: {message.body}")
        future.set_result(message)

    async def call(
        self, priority: int, threshold: int, model: str
    ) -> AbstractIncomingMessage | int:
        model_queue = await self.channel.get_queue(name=model)
        nb_messages = model_queue.declaration_result.message_count
        logging.debug(f"{nb_messages} messages in the model queue : {model}")
        if nb_messages > threshold:
            return 1

        logging.info(f"New request for model {model}")
        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        await self.channel.default_exchange.publish(
            message=Message(
                body=b"AVAILABLE?",
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
                priority=priority,
            ),
            routing_key=model,
        )
        logging.debug(f"Message pushed to model queue {model}")
        response: AbstractIncomingMessage = await future
        logging.info(f"Received URL for model {model}")
        return response

    async def check_connection(self):
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False
