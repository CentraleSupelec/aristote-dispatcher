import asyncio
import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue

from src.consumer.quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy
from src.consumer.quality_of_service_policy.utils import requeue
from src.consumer.settings import settings


class PerformanceBasedRequeuePolicy(QualityOfServiceBasePolicy):
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
            asyncio.create_task(
                requeue(message, exchange, queue=target_requeue, delay=delay)
            )
            return False
        return True
