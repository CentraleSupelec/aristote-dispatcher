import asyncio
import logging

from aio_pika import connect, Message, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue, AbstractIncomingMessage
from metrics_handler import metrics_handler
from settings import settings


# === Set constants ===

LLM_URL = settings.LLM_URL
MODEL = settings.MODEL

RABBITMQ_URL = settings.RABBITMQ_URL

AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD

DEFAULT_RETRY = 10
WAIT_TIME = 0.5


class RPCServer:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.queue: AbstractQueue = None
        self.consumer_tag = None
        self.rpc_exchange = None

    async def connect(self) -> None:
        logging.debug("Connecting consumer to RabbitMQ...")
        try:
            self.connection = await connect(url=self.url)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            self.queue = await self.channel.declare_queue(name=MODEL, durable=True)
            self.consumer_tag = await self.queue.consume(self.on_message_callback, no_ack=False)
        except Exception as e:
            logging.error(f"Error connecting to RabbitMQ: {e}")
            raise
        else:
            logging.info("Consumer connected to RabbitMQ")

    async def close(self) -> None:
        if self.queue and self.consumer_tag:
            await self.queue.cancel(self.consumer_tag)
            self.queue = None
            self.consumer_tag = None
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None

    async def on_message_callback(self, message: AbstractIncomingMessage):
        logging.info(f"Message consumed on queue {MODEL}")

        current_avg_token, current_nb_users = await metrics_handler.get_metrics()
        
        while current_avg_token < AVG_TOKEN_THRESHOLD and current_nb_users > NB_USER_THRESHOLD:
            await asyncio.sleep(WAIT_TIME)
            current_avg_token, current_nb_users = await metrics_handler.get_metrics()

        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=LLM_URL.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=str(message.correlation_id),
                ),
                routing_key=message.reply_to
            )
            logging.info(f"LLM URL for model {MODEL} sent to API")
        except Exception as e:
            logging.error(f"An error occured while publishing message: {e}")
            raise
        else:
            await message.ack()

    # WIP

    # async def check_connection(self) -> bool:
    #     if self.connection and self.channel:
    #         if not self.connection.is_closed and not self.channel.is_closed:
    #             return True
    #     return False
    
    # async def reconnect(self):
    #     logging.info("Attempting to reconnect RPC client...")
    #     try:
    #         await self.close()
    #         await self.connect()
    #         logging.info("RPC client reconnected successfully")
    #     except Exception as e:
    #         logging.error(f"Error while reconnecting RPC client: {e}")
    #         raise


rpc_server = RPCServer(url=RABBITMQ_URL)