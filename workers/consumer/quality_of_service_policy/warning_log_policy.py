import logging

from aio_pika.abc import AbstractIncomingMessage

from .qos_policy import QualityOfServiceBasePolicy


class WarningLogPolicy(QualityOfServiceBasePolicy):

    def apply_policy(
        self, performance_indicator: float | None, message: AbstractIncomingMessage
    ) -> bool:
        if (
            isinstance(performance_indicator, (float, int))
            and performance_indicator > self.performance_threshold
        ):
            logging.warning(
                "Performance indicator exceeds threshold (%s > %s)",
                performance_indicator,
                self.performance_threshold,
            )
        return True
