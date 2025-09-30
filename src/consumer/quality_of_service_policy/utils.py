import asyncio

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue


async def requeue(
    msg: AbstractIncomingMessage,
    exchange: AbstractExchange,
    queue: AbstractQueue | None = None,
    delay: int | None = None,
) -> None:
    """
    Requeue a message with an incremented retry counter.

    - If `queue` is provided, republishes directly there.
    - If no `queue` is provided, republishes to the original exchange/routing key
      after a delay (`settings.METRICS_REFRESH_RATE`).
    """
    headers = dict(msg.headers or {})
    headers["x-requeue-count"] = headers.get("x-requeue-count", 0) + 1

    new_msg = Message(
        body=msg.body,
        headers=headers,
        content_type=msg.content_type,
        correlation_id=msg.correlation_id,
        delivery_mode=msg.delivery_mode or DeliveryMode.PERSISTENT,
        priority=msg.priority,
        reply_to=msg.reply_to,
    )

    await msg.ack()

    if delay is not None:
        await asyncio.sleep(delay)

    if queue:
        routing_key = queue.name
    else:
        routing_key = msg.routing_key

    await exchange.publish(new_msg, routing_key=routing_key)
