import asyncio
import logging

from aio_pika import DeliveryMode, Exchange, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from ..settings import settings
from .qos_policy import QualityOfServiceBasePolicy


class RequeuePolicy(QualityOfServiceBasePolicy):

    async def _delayed_nack(self, msg: AbstractIncomingMessage):
        await asyncio.sleep(settings.METRICS_REFRESH_RATE)
        await msg.nack(requeue=True)

    async def _transfer_message(
        self, msg: AbstractIncomingMessage, queue: AbstractQueue, exchange: Exchange
    ):
        await asyncio.sleep(settings.METRICS_REFRESH_RATE)
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

    def apply_policy(
        self,
        performance_indicator: float | None,
        current_parallel_requests: int,
        max_parallel_requests: int,
        message: AbstractIncomingMessage | None = None,
        target_requeue: AbstractQueue | None = None,
        exchange: Exchange | None = None,
    ) -> bool:
        if isinstance(performance_indicator, (float, int)) and (
            (performance_indicator > self.performance_threshold)
            or (current_parallel_requests >= max_parallel_requests)
        ):
            logging.info(
                "QoS policy deferred the message; requeuing. performance_indicator: %s, self.performance_threshold: %s, current_parallel_requests: %s, max_parallel_requests: %s",
                performance_indicator,
                self.performance_threshold,
                current_parallel_requests,
                settings.MAX_PARALLEL_REQUESTS,
            )
            if target_requeue:
                asyncio.create_task(
                    self._transfer_message(message, target_requeue, exchange)
                )
            else:
                asyncio.create_task(self._delayed_nack(message))
            return False
        return True
