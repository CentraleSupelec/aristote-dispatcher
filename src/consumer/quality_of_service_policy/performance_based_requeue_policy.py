import asyncio
import logging

from aio_pika import Exchange
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from src.consumer.quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy
from src.consumer.quality_of_service_policy.utils import (
    send_delayed_nack,
    transfer_message_to_exchange,
)
from src.consumer.settings import settings


class PerformanceBasedRequeuePolicy(QualityOfServiceBasePolicy):
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
                    transfer_message_to_exchange(message, target_requeue, exchange)
                )
            else:
                asyncio.create_task(send_delayed_nack(message))
            return False
        return True
