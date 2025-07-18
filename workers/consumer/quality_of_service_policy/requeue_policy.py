import asyncio
import logging

from aio_pika.abc import AbstractIncomingMessage

from ..settings import settings
from .qos_policy import QualityOfServiceBasePolicy


class RequeuePolicy(QualityOfServiceBasePolicy):

    async def _delayed_nack(self, msg):
        await asyncio.sleep(settings.METRICS_REFRESH_RATE)
        await msg.nack(requeue=True)

    def apply_policy(
        self,
        performance_indicator: float | None,
        message: AbstractIncomingMessage,
        current_parallel_requests: int,
    ) -> bool:
        if isinstance(performance_indicator, (float, int)) and (
            (performance_indicator > self.performance_threshold)
            or (current_parallel_requests >= settings.MAX_PARALLEL_REQUESTS)
        ):
            logging.info("QoS policy deferred the message; requeuing.")
            asyncio.create_task(self._delayed_nack(message))
            return False
        return True
