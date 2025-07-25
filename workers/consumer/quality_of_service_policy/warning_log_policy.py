import logging

from aio_pika.abc import AbstractIncomingMessage

from ..settings import settings
from .qos_policy import QualityOfServiceBasePolicy


class WarningLogPolicy(QualityOfServiceBasePolicy):

    def apply_policy(
        self,
        performance_indicator: float | None,
        message: AbstractIncomingMessage,
        current_parallel_requests: int,
    ) -> bool:
        if isinstance(performance_indicator, (float, int)):
            if performance_indicator > self.performance_threshold:
                logging.warning(
                    "Performance indicator exceeds threshold (%s > %s)",
                    performance_indicator,
                    self.performance_threshold,
                )
            if current_parallel_requests >= settings.MAX_PARALLEL_REQUESTS:
                logging.warning(
                    "Too many requests waiting for vllm response: %s",
                    current_parallel_requests,
                )
        return True
