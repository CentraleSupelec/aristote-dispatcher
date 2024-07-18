import asyncio
import logging

from aio_pika import connect, Message, DeliveryMode
from aio_pika.abc import (
    AbstractConnection,
    AbstractChannel,
    AbstractQueue,
    AbstractIncomingMessage,
)
from metrics import try_update_metrics
from settings import settings


# === Set constants ===

LLM_URL = settings.LLM_URL
MODEL = settings.MODEL

RABBITMQ_URL = settings.RABBITMQ_URL

AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD

RPC_RECONNECT_ATTEMPTS = settings.RPC_RECONNECT_ATTEMPTS
WAIT_FOR_LLM_DELAY = 1


class RPCServer:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.queue: AbstractQueue = None

    async def connect(self) -> None:
        logging.debug("Connecting consumer to RabbitMQ...")
        try:
            self.connection = await connect(url=self.url)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            self.queue = await self.channel.declare_queue(
                name=MODEL,
                durable=True,
                arguments={
                    "x-expires": settings.RPC_QUEUE_EXPIRATION,
                },
            )
            self.consumer_tag = await self.queue.consume(
                self.on_message_callback,
                no_ack=True,
            )
            self.connection.close_callbacks.add(self.try_reconnect)
        except Exception as e:
            logging.error(f"Error connecting to RabbitMQ: {e}")
            raise
        else:
            logging.info("Consumer connected to RabbitMQ")

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

    async def on_message_callback(self, message: AbstractIncomingMessage):
        logging.debug(f"Message consumed on queue {MODEL}")

        current_avg_token, current_nb_users = await try_update_metrics()

        while (
            current_avg_token < AVG_TOKEN_THRESHOLD
            and current_nb_users > NB_USER_THRESHOLD
        ):
            await asyncio.sleep(WAIT_FOR_LLM_DELAY)
            current_avg_token, current_nb_users = await try_update_metrics()

        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=LLM_URL.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=str(message.correlation_id),
                ),
                routing_key=message.reply_to,
            )
            logging.info(f"LLM URL for model {MODEL} sent to API")
        except Exception as e:
            logging.error(f"An error occured while publishing message: {e}")
            raise

    async def check_connection(self) -> bool:
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False

    async def reconnect(self):
        logging.debug("Attempting to reconnect to RPC client...")
        try:
            await self.connect()
            logging.info("RPC client reconnected successfully")
        except Exception as e:
            logging.error(f"Error while reconnecting RPC client: {e}")
            raise

    # Function signature is required by close_callbacks
    async def try_reconnect(self, *args, **kwargs):
        for i in range(RPC_RECONNECT_ATTEMPTS):
            try:
                await self.reconnect()
            except Exception:
                logging.info(f"Attempt {i+1}/{RPC_RECONNECT_ATTEMPTS} to reconnect RPC client failed")
                await asyncio.sleep(i)
            else:
                break
        else:
            raise Exception(f"Failed to reconnect to RPC client after {RPC_RECONNECT_ATTEMPTS} attempts")


rpc_server = RPCServer(url=RABBITMQ_URL)
