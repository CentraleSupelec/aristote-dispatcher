import logging
import asyncio
import uuid
from aio_pika import connect, Message, DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue, AbstractIncomingMessage
from typing import MutableMapping
from settings import Settings


class RPCClient:
    connection: AbstractConnection
    channel: AbstractChannel
    callback_queue: AbstractQueue
    settings: Settings

    def __init__(self, settings: Settings) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.settings = settings

    async def connect(self) -> None:
        self.connection = await connect(url=self.settings.RABBITMQ_URL)
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
        logging.info(f"Got response {message.body}")
        future.set_result(message)

    async def call(self, priority: int, threshold: int, model: str) -> AbstractIncomingMessage | int:
        model_queue = await self.channel.get_queue(name=model)
        nb_messages = model_queue.declaration_result.message_count            
        logging.info(f"{nb_messages} messages in the model queue : {model}")
        if nb_messages > threshold:
            return 1
        
        logging.info(f"New request for model {model}")
        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        await self.channel.default_exchange.publish(
            message = Message(
                body=b"AVAILABLE?",
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
                priority=priority
            ),
            routing_key=model,
        )
        logging.info(f"Message push to model queue {model}")
        response: AbstractIncomingMessage = await future
        logging.info(f"For model {model}, got LLM URL")
        return response