import asyncio

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue

from src.consumer.quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy
from src.consumer.quality_of_service_policy.utils import requeue
from src.consumer.settings import settings


class ParallelRequestsThresholdRequeuePolicy(QualityOfServiceBasePolicy):
    def apply_policy(
        self,
        performance_indicator: float | None,
        current_parallel_requests: int,
        max_parallel_requests: int,
        exchange: AbstractExchange,
        message: AbstractIncomingMessage | None = None,
        target_requeue: AbstractQueue | None = None,
        delay: int | None = None,
    ) -> bool:
        if (
            isinstance(message.priority, int)
            and message.priority >= settings.BEST_PRIORITY - 1
        ):
            return True

        if current_parallel_requests >= max_parallel_requests:
            asyncio.create_task(
                requeue(message, exchange, queue=target_requeue, delay=delay)
            )

            return False

        return True
