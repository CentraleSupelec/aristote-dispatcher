import asyncio
import logging

from aio_pika import connect, Message, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue, AbstractIncomingMessage
from settings import settings
from typing import MutableMapping


# === Set constants ===

LLM_URL = settings.LLM_URL
MODEL = settings.MODEL


class RPCClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.callback_queue: AbstractQueue = None
        self.consumer_tag = None
        self.futures: MutableMapping[str, asyncio.Future] = {}

    async def connect(self) -> None:
        try:
            self.connection = await connect(url=self.url)
            self.channel = await self.connection.channel()
            self.callback_queue = await self.channel.declare_queue(exclusive=True)
            self.consumer_tag = await self.callback_queue.consume(self.on_response, no_ack=True)
        except Exception as e:
            logging.error(f"Erreur en se connectant à RabbitMQ: {e}")
            raise

    async def close(self) -> None:
        if self.consumer_tag:
            await self.callback_queue.cancel(self.consumer_tag)
        if self.connection:
            await self.connection.close()

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        logging.debug(f"Message reçu avec un ID de corrélation : {message.correlation_id}")
        if message.correlation_id:
            future = self.futures.pop(message.correlation_id, None)
            if future:
                future.set_result(message)
                logging.info(f"Le Future avec un ID de corrélation {message.correlation_id} a été définie")
            else:
                logging.error(f"Aucun Future trouvé avec un ID de corrélation {message.correlation_id}")
        else:
            logging.error(f"Message reçu sans ID de corrélation: {message!r}")

    async def call(self, routing_key: str, correlation_id: str) -> AbstractIncomingMessage:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=LLM_URL.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=correlation_id,
                    reply_to=self.callback_queue.name
                ),
                routing_key
            )
            logging.info(f"URL du LLM pour le modèle {MODEL} envoyée à l'API")
        except Exception as e:
            logging.error(f"Une erreur est survenue en publiant le message : {e}")
            raise

        return await future
