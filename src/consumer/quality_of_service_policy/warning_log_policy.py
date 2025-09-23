import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue

from src.consumer.quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy


class WarningLogPolicy(QualityOfServiceBasePolicy):

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
        if isinstance(performance_indicator, (float, int)):
            if performance_indicator > self.performance_threshold:
                logging.warning(
                    "Performance indicator exceeds threshold (%s > %s)",
                    performance_indicator,
                    self.performance_threshold,
                )
            if current_parallel_requests >= max_parallel_requests:
                logging.warning(
                    "Too many requests waiting for vllm response: %s",
                    current_parallel_requests,
                )
        return True
