import asyncio

from aio_pika import Exchange, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue, DeliveryMode

from src.consumer.settings import settings


async def send_delayed_nack(msg: AbstractIncomingMessage):
    await asyncio.sleep(settings.METRICS_REFRESH_RATE)
    await msg.nack(requeue=True)


async def transfer_message_to_exchange(
    msg: AbstractIncomingMessage, queue: AbstractQueue, exchange: Exchange
):
    await exchange.publish(
        message=Message(
            body=b"AVAILABLE?",
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=msg.correlation_id,
            reply_to=msg.reply_to,
            priority=msg.priority,
        ),
        routing_key=queue.name,
    )
    await msg.ack()
