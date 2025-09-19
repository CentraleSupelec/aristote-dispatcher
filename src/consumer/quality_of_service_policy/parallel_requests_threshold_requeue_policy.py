import asyncio

from aio_pika import Exchange
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from src.consumer.quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy
from src.consumer.quality_of_service_policy.utils import (
    send_delayed_nack,
    transfer_message_to_exchange,
)
from src.consumer.settings import settings


class ParallelRequestsThresholdRequeuePolicy(QualityOfServiceBasePolicy):
    def apply_policy(
        self,
        performance_indicator: float | None,
        current_parallel_requests: int,
        max_parallel_requests: int,
        message: AbstractIncomingMessage | None = None,
        target_requeue: AbstractQueue | None = None,
        exchange: Exchange | None = None,
    ) -> bool:
        if (
            isinstance(message.priority, int)
            and message.priority >= settings.BEST_PRIORITY - 1
        ):
            return True

        if current_parallel_requests >= max_parallel_requests:
            if target_requeue:
                asyncio.create_task(
                    transfer_message_to_exchange(message, target_requeue, exchange)
                )
            else:
                asyncio.create_task(send_delayed_nack(message))
            return False

        return True
